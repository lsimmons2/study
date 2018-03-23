
import random
import sys
import re
import json
import subprocess
import os
import signal



class StudyBuddy(object):


    def __init__(self, file_path=None, show_all=False, success_rate_threshold=1.00, just_show_statistics=False):
        self.file_path = file_path
        self.show_all = show_all
        self.success_rate_threshold = success_rate_threshold
        self.just_show_statistics = just_show_statistics
        self.images = []
        self._write_file_with_ids()
        self._set_points()
        self._read_metadata()
        self._filter_points_to_study()


    def _get_point_id(self, line):
        try:
            return int(re.search(r'\? (\d+)$', line).group(1))
        except AttributeError:
            return None


    def _get_file_lines(self):
        with open(self.file_path, 'r') as f:
            return f.read().splitlines()


    def _write_file_with_ids(self):
        # will collect these for use in self._read_metadata()
        self.file_point_ids = []
        new_file_str = ''
        last_id = 0
        file_lines = self._get_file_lines()
        comment_lines = []
        for line in file_lines:
            if not self._is_comment(line):
                line_id = self._get_point_id(line)
                if line_id:
                    last_id = line_id
                # if ends with ? then doesn't end with id, and needs to
                if line.strip().endswith('?'):
                    new_id = last_id + 1
                    line = line + ' ' + str(new_id)
                    last_id = new_id
                new_file_str += line + '\n'
                self.file_point_ids.append(last_id)
            else:
                comment_lines.append(line)
        if len(comment_lines):
            new_file_str += '\n\n'
        for comment_line in comment_lines:
            new_file_str += comment_line + '\n'
        with open(self.file_path, 'w') as f:
            f.write(new_file_str)
    

    def _is_comment(self, line):
        if line.startswith('-'):
            return True
        if line.startswith('*'):
            return True
        return False


    def _read_metadata(self):
        metadata_file_path = self._get_metadata_file_path()
        try:
            with open(metadata_file_path, 'r') as f:
                self.metadata = json.load(f)
            metadata_point_ids = self.metadata.keys()
            for point_id in self.file_point_ids:
                if point_id not in metadata_point_ids:
                    self.metadata[point_id] = self._get_default_metadata()
        except (IOError, ValueError):
            # metadata file hasn't been created or isn't json
            self.metadata = {}
            for point in self.points:
                point_id = str(point['point_id'])
                self.metadata[point_id] = self._get_default_metadata()


    def _get_default_metadata(self):
        return {
            'successful_guess_count': 0,
            'total_guess_count': 0,
            'is_hidden': False
        }


    def _get_metadata_file_path(self):
        file_path_parts = self.file_path.split('/')
        metadata_file_name = '.' + file_path_parts[-1].split('.')[0] + '.json'
        if len(file_path_parts) < 2:
            # file is in cwd
            metadata_file_path = metadata_file_name
        else:
            metadata_file_path = '/'.join(file_path_parts[:-1]) + '/' + metadata_file_name
        return metadata_file_path


    def _is_question_line(self, line):
        if self._is_comment(line):
            return False
        line_point_id = self._get_point_id(line)
        # question lines will have a point_id after self._write_file_with_ids()
        return bool(line_point_id)


    def _is_image_path(self, string):
        return '.png' in string


    def _set_points(self):
        all_lines = self._get_file_lines()
        self.points = []
        for index, line in enumerate(all_lines):
            if self._is_question_line(line):
                point_id = self._get_point_id(line)
                question_is_image = self._is_image_path(line)
                if question_is_image:
                    question = line[:-3] # remove id and question mark from question line
                else:
                    question = line[:-2] # just remove id
                answer = all_lines[index+1] # answer should be line after question line
                answer_is_image = self._is_image_path(answer)
                new_point = {
                    'point_id': point_id,
                    'question': question,
                    'question_is_image': question_is_image,
                    'answer_is_image': answer_is_image,
                    'answer': answer
                }
                self.points.append(new_point)


    def _filter_points_to_study(self):
        self.points_to_study = [ point for point in self.points if self._should_study_point(point) ]


    def _should_study_point(self, point):
        point_metadata = self._get_point_metadata(point['point_id'])
        point_success_rate = self._get_point_success_rate(point)
        if point_metadata['total_guess_count'] < 3:
            return True
        if point_success_rate >= self.success_rate_threshold:
            return False
        if point_metadata['is_hidden'] and not self.show_all:
            return False
        return True


    def _get_point_success_rate(self, point):
        point_metadata = self._get_point_metadata(point['point_id'])
        try:
            return float(point_metadata['successful_guess_count']) / point_metadata['total_guess_count']
        except ZeroDivisionError:
            return 0.00


    def _handle_response(self, point):
        response = raw_input()
        point_metadata = self._get_point_metadata(point['point_id'])
        if response == 'h':
            point_metadata['is_hidden'] = True
        elif response == 'y' or response == 'c':
            point_metadata['successful_guess_count'] += 1
            point_metadata['total_guess_count'] += 1
        elif response == 'n' or response == 'i':
            point_metadata['total_guess_count'] += 1
        elif response == 'p':
            print 'Passing...'
        else:
            print 'Mark correct or not'
            return self._handle_response(point)


    def _get_point_metadata(self, point_id):
        return self.metadata[str(point_id)]


    def _save_metadata(self):
        metadata_file_path = self._get_metadata_file_path()
        with open(metadata_file_path, 'w') as f:
            json.dump(self.metadata, f, indent=2)


    def _show_statistics(self):
        for point in self.points:
            print
            print point['question']
            point_metadata = self._get_point_metadata(point['point_id'])
            success_rate = self._get_point_success_rate(point)
            print '%d / %d = %.2f' % (point_metadata['successful_guess_count'],
                                      point_metadata['total_guess_count'],
                                      success_rate)


    def _study_point(self, point):
        print '\n'
        if point['question_is_image']:
            question_image = PointImage(point['question'])
            question_image.open()
            self.images.append(question_image)
        else:
            print point['question']
        raw_input()
        if point['answer_is_image']:
            answer_image = PointImage(point['answer'])
            answer_image.open()
            self.images.append(answer_image)
        else:
            print point['answer']
        self._handle_response(point)
        self._close_images()


    def _close_images(self):
        for image in self.images:
            image.close()


    def study(self):
        if self.just_show_statistics:
            return self._show_statistics()
        try:
            for point in self.points_to_study:
                self._study_point(point)
            self._save_metadata()
        except KeyboardInterrupt:
            self._close_images()



class PointImage(object):

    '''passed a file path of an image at start up closes and opens said image'''

    def __init__(self, image_path):
        self.image_path = image_path

    def open(self):
        open_image_cmd = 'gnome-open %s' % self.image_path
        self.process = subprocess.Popen(open_image_cmd,
                                        shell=True,
                                        stdout=subprocess.PIPE,
                                        preexec_fn=os.setsid)

    def close(self):
        pid = os.getpgid(self.process.pid)
        os.killpg(pid, signal.SIGTERM)



def get_options():
    args = sys.argv[1:]
    file_path = args[-1]
    options = {'file_path': file_path}
    if '-a' in args:
        options['show_all'] = True
    if '-t' in args:
        options['success_rate_threshold'] = float(args[args.index('-t') + 1])
    if '-s' in args:
        options['just_show_statistics'] = True
    return options



if __name__ == '__main__':
    options = get_options()
    buddy = StudyBuddy(**options)
    buddy.study()
