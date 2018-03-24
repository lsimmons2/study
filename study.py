
import sys
import re
import json
import subprocess
import os
import signal



class StudyBuddy(object):


    def __init__(self, study_file_path=None, show_all=False, success_rate_threshold=1.00, just_show_statistics=False):
        self.study_file_path = study_file_path
        self.show_all = show_all
        self.success_rate_threshold = success_rate_threshold
        self.just_show_statistics = just_show_statistics

        self.metadata_file_path = self._get_metadata_file_path()
        self._check_metadata_file()
        self.highest_point_id = self._get_highest_point_id()
        self._write_file_with_ids()

        self._set_points()
        self._filter_points_to_study()


    def _get_highest_point_id(self):
        with open(self.metadata_file_path, 'r') as f:
            all_points_metadata = json.load(f)
        point_ids = [ int(point_id) for point_id in all_points_metadata.keys() ]
        try:
            return sorted([])[-1]
        except IndexError:
            return 0


    def _get_metadata_file_path(self):
        return os.path.expanduser('~') + '/.study_metadata.json'


    def _check_metadata_file(self):
        try:
            with open(self.metadata_file_path, 'r') as f:
                json.load(f)
        except IOError:
            with open(self.metadata_file_path, 'w') as f:
                print 'Creating empty metadata file %s.' % self.metadata_file_path
                json.dump({}, f)
        except ValueError:
            raise Exception('Metadata file %s is messed up and isn\'t proper JSON.' % self.metadata_file_path)


    def _get_point_id(self, line):
        try:
            return int(re.search(r'\? (\d+)$', line).group(1))
        except AttributeError:
            return None


    def _get_file_lines(self):
        with open(self.study_file_path, 'r') as f:
            return f.read().splitlines()


    def _write_file_with_ids(self):
        new_file_str = ''
        last_id = self.highest_point_id
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
            else:
                comment_lines.append(line)
        # comment_lines are pushed to bottom of file
        for comment_line in comment_lines:
            new_file_str += comment_line + '\n'
        with open(self.study_file_path, 'w') as f:
            f.write(new_file_str)
    

    def _is_comment(self, line):
        if line.startswith('-'):
            return True
        if line.startswith('*'):
            return True
        return False


    def _is_question_line(self, line):
        if self._is_comment(line):
            return False
        line_point_id = self._get_point_id(line)
        # question lines will have a point_id after self._write_file_with_ids()
        return bool(line_point_id)


    def _set_points(self):
        all_lines = self._get_file_lines()
        self.points = []
        for index, line in enumerate(all_lines):
            if self._is_question_line(line):
                question_line = line
                answer_line = all_lines[index+1] # answer should be line after question line
                point_id = self._get_point_id(line)
                new_point = Point(question_line, answer_line, point_id, self.metadata_file_path)
                self.points.append(new_point)


    def _filter_points_to_study(self):
        self.points_to_study = [ point for point in self.points if self._should_study_point(point) ]

            
    def _should_study_point(self, point):
        if point.total_guess_count < 3:
            return True
        if point.get_success_rate() >= self.success_rate_threshold:
            return False
        if point.is_hidden and not self.show_all:
            return False
        return True


    def _show_statistics(self):
        for point in self.points:
            print
            print point.question
            print '%d / %d = %.2f' % (point.successful_guess_count,
                                      point.total_guess_count,
                                      point.get_success_rate())


    def study(self):
        if self.just_show_statistics:
            return self._show_statistics()
        try:
            for point in self.points_to_study:
                point.study()
        except KeyboardInterrupt:
            print '\nExiting early'
        for point in self.points:
            point.tear_down()



class Point(object):


    def __init__(self, question_line, answer_line, point_id, metadata_file_path):
        self.question_line = question_line
        self.answer = answer_line
        self.id = point_id
        self.question_is_image = self._is_image_path(question_line)
        self.answer_is_image = self._is_image_path(answer_line)
        self._trim_question_line()
        self.metadata_file_path = metadata_file_path
        self._read_metadata()
        self.images = []


    def study(self):
        print '\n'
        if self.question_is_image:
            question_image = PointImage(self.question)
            question_image.open()
            self.images.append(question_image)
        else:
            print self.question
        raw_input()
        if self.answer_is_image:
            answer_image = PointImage(self.answer)
            answer_image.open()
            self.images.append(answer_image)
        else:
            print self.answer
        self._handle_response()
        self._close_images()


    def _trim_question_line(self):
        question_end_index = self.question_line.rfind('?')
        if self.question_is_image:
            # can't have point id or ? in an image path
            self.question = self.question_line[:question_end_index:]
        else:
            # don't want the point id displayed when asking question
            self.question = self.question_line[:question_end_index]


    def tear_down(self):
        self._save_metadata()
        self._close_images()


    def _close_images(self):
        for image in self.images:
            image.close()


    def _save_metadata(self):
        updated_metadata = {}
        for attr in self._get_default_metadata().keys():
            updated_metadata[attr] = getattr(self, attr)
        with open(self.metadata_file_path, 'r') as f:
            all_points_metadata = json.load(f)
        all_points_metadata[str(self.id)] = updated_metadata
        with open(self.metadata_file_path, 'w') as f:
            json.dump(all_points_metadata, f, indent=2)


    def _handle_response(self):
        response = raw_input()
        if response == 'h':
            self.is_hidden = True
        elif response == 'y' or response == 'c':
            self.successful_guess_count += 1
            self.total_guess_count += 1
        elif response == 'n' or response == 'i':
            self.total_guess_count += 1
        elif response == 'p':
            print 'Passing...'
        else:
            print 'Mark correct or not'
            return self._handle_response()


    def _read_metadata(self):
        with open(self.metadata_file_path, 'r') as f:
            all_points_metadata = json.load(f)
        try:
            point_metadata = all_points_metadata[str(self.id)]
        except KeyError:
            point_metadata = self._get_default_metadata()
        # get attrs from default dict in case more fields are added
        default_metadata = self._get_default_metadata()
        for attr in default_metadata.keys():
            try:
                setattr(self, attr, point_metadata[attr])
            except KeyError:
                # if field has been added to default metadata since point has
                # been saved - give point default value of new field
                setattr(self, attr, default_metadata[attr])


    def _get_default_metadata(self):
        return {
            'total_guess_count': 0,
            'successful_guess_count': 0,
            'is_hidden': False
        }


    def _is_image_path(self, string):
        return '.png' in string


    def get_success_rate(self):
        try:
            return float(self.successful_guess_count) / self.total_guess_count
        except ZeroDivisionError:
            return 0.00



class PointImage(object):

    '''passed a file path of an image at start up, opens and closes said image'''

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
    study_file_path = args[-1]
    options = {'study_file_path': study_file_path}
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
