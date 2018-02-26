

import random
import sys
import re
import json



class StudyBuddy(object):


    def __init__(self, file_path=None, show_all=False, success_rate_threshold=1.00):
        self.file_path = file_path
        self.show_all = show_all
        self.success_rate_threshold = success_rate_threshold
        self._write_file_with_ids()
        self._set_points()
        self._read_metadata()
        self._filter_points_under_threshold()


    def _get_point_id(self, line):
        try:
            return int(re.search(r'\? (\d+)$', line).group(1))
        except AttributeError:
            return None


    def _write_file_with_ids(self):
        new_file_str = ''
        last_id = 0
        with open(self.file_path, 'r') as f:
            for line in f.read().splitlines():
                if self._is_point_line(line):
                    line_id = self._get_point_id(line)
                    if line_id:
                        last_id = line_id
                    # if ends with ? then doesn't end with id, and needs to
                    if line.strip().endswith('?'):
                        new_id = last_id + 1
                        line = line + ' ' + str(new_id)
                        last_id = new_id
                new_file_str += line + '\n'
        with open(self.file_path, 'w') as f:
            f.write(new_file_str)
    

    def _is_point_line(self, line):
        if line.startswith('-'):
            return False
        if line.startswith('*'):
            return False
        if not len(line):
            return False
        return True


    def _read_metadata(self):
        metadata_file_path = self._get_metadata_file_path()
        try:
            with open(metadata_file_path, 'r') as f:
                self.metadata = json.load(f)
        except (IOError, ValueError):
            # metadata file hasn't been created or isn't json
            self.metadata = {}
            for point in self.points:
                point_id = str(point['point_id'])
                self.metadata[point_id] = {
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


    def _set_points(self):
        with open(self.file_path, 'r') as f:
            all_lines = f.read().splitlines()
        point_lines = []
        for line in all_lines:
            if self._is_point_line(line):
                point_lines.append(line)
        self.points = []
        new_point = {}
        for line in point_lines:
            if 'question' not in new_point:
                question = line[:-2] # remove id from question line
                point_id = self._get_point_id(line)
                new_point = {'question': question, 'point_id': point_id}
            else:
                new_point['answer'] = line
                self.points.append(new_point)
                new_point = {}


    def _filter_points_under_threshold(self):
        points_under_threshold = []
        for point in self.points:
            point_metadata = self._get_point_metadata(point['point_id'])
            try:
                point_success_rate = point_metadata['successful_guess_count'] / point_metadata['total_guess_count']
            except ZeroDivisionError:
                point_success_rate = 0
            if point_success_rate < self.success_rate_threshold\
                    and (not point_metadata['is_hidden'] or self.show_all):
                points_under_threshold.append(point)
        self.points = points_under_threshold


    def _handle_response(self, point):
        response = raw_input()
        point_metadata = self._get_point_metadata(point['point_id'])
        if response == 'h':
            point_metadata['is_hidden'] = True
        elif response == 'y':
            point_metadata['successful_guess_count'] += 1
            point_metadata['total_guess_count'] += 1
        elif response == 'n':
            point_metadata['total_guess_count'] += 1
        elif response == 'i':
            print 'Ignoring...'
        else:
            print 'Mark correct or not'
            return self._handle_response(point)


    def _get_point_metadata(self, point_id):
        return self.metadata[str(point_id)]


    def _save_metadata(self):
        metadata_file_path = self._get_metadata_file_path()
        with open(metadata_file_path, 'w') as f:
            json.dump(self.metadata, f, indent=2)


    def study(self):
        random.shuffle(self.points)
        for point in self.points:
            print '\n'
            print point['question']
            raw_input()
            print point['answer']
            self._handle_response(point)
        self._save_metadata()



def get_options():
    args = sys.argv[1:]
    file_path = args[0]
    options = {'file_path': file_path}
    if '-a' in args:
        options['show_all'] = True
    if '-s' in args:
        options['success_rate_threshold'] = float(args[args.index('-s') + 1])
    return options



if __name__ == '__main__':
    options = get_options()
    buddy = StudyBuddy(**options)
    buddy.study()
