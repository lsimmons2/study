
import sys
import re
import json
import subprocess
import os
import signal
import collections



class StudyBuddy(object):


    def __init__(self, study_file_paths=None, show_all=False, success_rate_threshold=0.8, just_show_statistics=False, just_show_uncertainties=False):
        self.study_file_paths = study_file_paths
        self.show_all = show_all
        self.success_rate_threshold = success_rate_threshold
        self.just_show_statistics = just_show_statistics
        self.just_show_uncertainties = just_show_uncertainties
        self.metadata_file_path = Config.METADATA_FILE_PATH
        self._check_metadata_file()
        self._sync_points_to_metadata_file()
        self._format_study_files()
        self._collect_all_points()
        self._filter_and_sort_points_to_study()


    def _sync_points_to_metadata_file(self):
        all_point_ids = []
        for line in self._get_file_lines():
            point_id = self._get_point_id(line)
            if point_id:
                all_point_ids.append(point_id)
        if len(all_point_ids) != len(set(all_point_ids)):
            raise Exception('There are duplicate point ids in study files.')
        metadata = self._get_current_metadata()
        for point_id in all_point_ids:
            if str(point_id) not in metadata:
                metadata[str(point_id)] = Point.default_metadata
        self._overwrite_metadata_file(metadata)


    def _get_current_metadata(self):
        with open(self.metadata_file_path, 'r') as f:
            return json.load(f, object_pairs_hook=collections.OrderedDict)


    def _overwrite_metadata_file(self, new_metadata):
        with open(self.metadata_file_path, 'w') as f:
            json.dump(new_metadata, f, indent=2)


    def _get_highest_point_id(self):
        with open(self.metadata_file_path, 'r') as f:
            all_points_metadata = json.load(f)
        point_ids = [ int(point_id) for point_id in all_points_metadata.keys() ]
        try:
            return sorted(point_ids)[-1]
        except IndexError:
            return 0


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


    def _get_file_lines(self, specific_file_path=None):
        if specific_file_path:
            study_file_paths = [specific_file_path]
        else:
            study_file_paths = self.study_file_paths # all of study buddy's files
        all_files_lines = []
        for file_path in study_file_paths:
            with open(file_path, 'r') as f:
                all_files_lines = all_files_lines + f.read().splitlines()
        return all_files_lines


    def _format_study_files(self):
        ''' rewrites all study files ensuring in each one that all question
        lines end with an id '''
        self.highest_point_id = self._get_highest_point_id()
        for file_path in self.study_file_paths:
            new_file_str = ''
            for line in self._get_file_lines(specific_file_path=file_path):
                if self._is_point_line(line):
                    # if ends with ? then doesn't end with id, and needs to
                    if line.strip().endswith('?'):
                        print 'yaaaaaaaa'
                        new_id = self.highest_point_id + 1
                        print new_id
                        line = line + ' ' + str(new_id)
                        self.highest_point_id = new_id
                new_file_str += line + '\n'
            with open(file_path, 'w') as f:
                f.write(new_file_str)


    def _is_point_line(self, line):
        if self._is_study_shebang(line):
            return False
        if self._is_note(line):
            return False
        if self._is_uncertainty(line):
            return False
        return True


    def _is_note(self, line):
        return line.strip().startswith('-')


    def _is_uncertainty(self, line):
        if line.strip().startswith('*') and not self._is_study_shebang(line):
            return True
        return False


    def _is_study_shebang(self, line):
        return line.strip() == '*study'


    def _is_question_line(self, line):
        if self._is_study_shebang(line):
            return False
        if self._is_uncertainty(line):
            return False
        if self._is_note(line):
            return False
        line_point_id = self._get_point_id(line)
        # question lines will have a point_id
        # after self._format_study_files()
        return bool(line_point_id)


    def _collect_all_points(self):
        self.points_by_file = {}
        for file_path in self.study_file_paths:
            self.points_by_file[file_path] = []
            file_lines = self._get_file_lines(specific_file_path=file_path)
            for index, line in enumerate(file_lines):
                if self._is_question_line(line):
                    question_line = line
                    answer_line = file_lines[index+1] # answer should be line after question line
                    point_id = self._get_point_id(line)
                    new_point = Point(question_line, answer_line, point_id)
                    self.points_by_file[file_path].append(new_point)


    def _filter_and_sort_points_to_study(self):
        for file_path in self.points_by_file:
            self.points_by_file[file_path] = [ p for p in self.points_by_file[file_path] if self._should_study_point(p) ]
            self.points_by_file[file_path].sort(key=lambda x: (x.total_attempt_count, x.success_rate))

            
    def _should_study_point(self, point):
        if point.is_hidden and not self.show_all:
            return False
        if point.total_attempt_count < 3:
            return True
        if point.success_rate > self.success_rate_threshold:
            return False
        return True


    def _show_all_point_stats(self):
        for point in self.points:
            print
            print point.question
            print '%d / %d = %.2f' % (point.successful_attempt_count,
                                      point.total_attempt_count,
                                      point.success_rate)


    def _get_seen_points(self):
        seen_points = []
        for file_path in self.points_by_file:
            for point in self.points_by_file[file_path]:
                if point.was_attempted or point.was_passed:
                    seen_points.append(point)
        return seen_points


    def _show_study_session_stats(self):
        points_seen = self._get_seen_points()
        successful_attempt_count = 0
        pass_count = 0
        for point in points_seen:
            if point.was_attempted_successfully:
                successful_attempt_count += 1
            elif point.was_passed:
                pass_count += 1
        total_attempt_count = len(points_seen) - pass_count
        stats_str = '\n%d points attempted, %d answered correctly.' % (total_attempt_count,
                                                                       successful_attempt_count)
        if pass_count:
            stats_str = '%s, %d passed.' % (stats_str[:-1], pass_count)
        print stats_str


    def _show_uncertainties(self):
        for file_path in self.study_file_paths:
            file_uncertainties = self._get_study_file_uncertainties(file_path)
            if file_uncertainties:
                print '\n%s' % file_path
                for q in file_uncertainties:
                    print q


    def _get_study_file_uncertainties(self, file_path):
        uncertainties = []
        with open(file_path, 'r') as f:
            lines = f.read().splitlines()
        for line in lines:
            if self._is_uncertainty(line):
                uncertainties.append(line)
        return uncertainties


    def study(self):
        if self.just_show_statistics:
            return self._show_all_point_stats()
        if self.just_show_uncertainties:
            return self._show_uncertainties()
        try:
            for file_path in self.points_by_file:
                print '\n%s' % file_path
                for point in self.points_by_file[file_path]:
                    point.study()
        except KeyboardInterrupt:
            print '\nExiting early'
        self._tear_down()
        self._show_study_session_stats()


    def _tear_down(self):
        ''' tearing down here and not in Point because saving each point in Point
        wouldn't work (not all points were saved before program exited), also
        reading and writing the metadata file in each point is inefficient '''
        metadata = self._get_current_metadata()
        seen_points = self._get_seen_points()
        for point in seen_points:
            point.close_images()
            metadata[str(point.id)] = point.get_metadata()
        self._overwrite_metadata_file(metadata)




class Point(object):


    default_metadata = {
        'total_attempt_count': 0,
        'successful_attempt_count': 0,
        'is_hidden': False
    }


    def __init__(self, question_line, answer_line, point_id):
        self.question_line = question_line
        self.answer = answer_line
        self.id = point_id
        self.question_is_image = self._is_image_path(question_line)
        self.answer_is_image = self._is_image_path(answer_line)
        self._trim_question_line()
        self.metadata_file_path = Config.METADATA_FILE_PATH
        self._read_metadata()
        self.success_rate = self._get_success_rate()
        self.images = []
        self.was_attempted = False
        self.was_attempted_successfully = False
        self.was_passed = False


    def __str__(self):
        if self.question_is_image:
            question_snippet = self.question
        else:
            question_snippet = '"%s...?"' % self.question[:25]
        return '<Point %d %s>' % (self.id, question_snippet)


    def study(self):
        print '\n'
        if self.question_is_image:
            print 'QUESTION IMAGE %s %d' % (self.question, self.id)
            question_image = PointImage(self.question)
            question_image.open()
            self.images.append(question_image)
        else:
            print '%s %d' % (self.question, self.id)
        raw_input()
        if self.answer_is_image:
            print 'ANSWER IMAGE %s' % self.answer
            answer_image = PointImage(self.answer)
            answer_image.open()
            self.images.append(answer_image)
        else:
            print self.answer
        self._handle_response()
        self.close_images()


    def _trim_question_line(self):
        question_end_index = self.question_line.rfind('?')
        if self.question_is_image:
            # can't have point id or ? in an image path
            self.question = self.question_line[:question_end_index:]
        else:
            # don't store the id with the question text
            self.question = self.question_line[:question_end_index+1]


    def get_metadata(self):
        updated_metadata = {}
        for attr in self.default_metadata.keys():
            updated_metadata[attr] = getattr(self, attr)
        if self.was_attempted:
            updated_metadata['total_attempt_count'] += 1
        if self.was_attempted_successfully:
            updated_metadata['successful_attempt_count'] += 1
        return updated_metadata


    def close_images(self):
        for image in self.images:
            image.close()


    def _handle_response(self):
        response = raw_input()
        if response == 'h':
            self.is_hidden = True
        elif response == 'y' or response == 'c':
            self.was_attempted = True
            self.was_attempted_successfully = True
        elif response == 'n' or response == 'i':
            self.was_attempted = True
        elif response == 'p':
            print 'Passing...'
            self.was_passed = True
        else:
            print 'Mark correct or not'
            return self._handle_response()


    def _read_metadata(self):
        with open(self.metadata_file_path, 'r') as f:
            all_points_metadata = json.load(f)
        point_metadata = all_points_metadata[str(self.id)]
        # get attrs from default dict in case more fields are added
        for attr in self.default_metadata.keys():
            try:
                setattr(self, attr, point_metadata[attr])
            except KeyError:
                # if field has been added to default metadata since point has
                # been saved - give point default value of new field
                setattr(self, attr, self.default_metadata[attr])


    def _is_image_path(self, string):
        return '.png' in string


    def _get_success_rate(self):
        try:
            return float(self.successful_attempt_count) / self.total_attempt_count
        except ZeroDivisionError:
            return 0.00



class PointImage(object):

    ''' passed a file path of an image at start up, opens and closes said image '''

    def __init__(self, image_file_name):
        self.image_path = '%s/%s' % (Config.IMAGES_DIR, image_file_name)

    def open(self):
        open_image_cmd = 'gnome-open %s' % self.image_path
        self.process = subprocess.Popen(open_image_cmd,
                                        shell=True,
                                        stdout=subprocess.PIPE,
                                        preexec_fn=os.setsid)

    def close(self):
        pid = os.getpgid(self.process.pid)
        os.killpg(pid, signal.SIGTERM)



class Config(object):

    IMAGES_DIR = os.getenv('STUDY_IMAGES_DIR')
    METADATA_FILE_PATH = os.getenv('METADATA_FILE_PATH')
    STUDY_BASE_DIR = os.getenv('STUDY_BASE_DIR')



def is_study_file(file_path):
    ''' to be a study file, file has to be a .txt file and
    have a study "shebang" at the top of the file '''
    if not file_path.endswith('.txt'):
        return False
    with open(file_path, 'r') as f:
        file_text = f.read()
    file_lines = file_text.splitlines()
    for line in file_lines:
        # study shebang has to be before any lines of text
        if line:
            if line.strip() == '*study':
                return True
            return False
    return False


def get_study_file_paths(args):
    study_file_paths = []
    for arg in args:
        # if you explicitly specify a .txt file, then consider it a study file
        if arg.endswith('.txt'):
            file_path = os.path.abspath(arg)
            study_file_paths.append(file_path)
        # if you give a directory, recursively search it looking for files that
        # fit critera set in is_study_file()
        elif os.path.isdir(arg):
            for directory, sub_directories, files in os.walk(arg):
                for file_name in files:
                    file_path = os.path.abspath(os.path.join(directory, file_name))
                    if is_study_file(file_path):
                        study_file_paths.append(file_path)
    if not study_file_paths:
        if Config.STUDY_BASE_DIR:
            print 'Searching for study files...'
            return get_study_file_paths([Config.STUDY_BASE_DIR])
        else:
            print 'Need to specify file or dir to study or set STUDY_BASE_DIR environmental variable.'
    return list(set(study_file_paths))


def get_options():
    args = sys.argv[1:]
    study_file_paths = get_study_file_paths(args)
    options = {'study_file_paths': study_file_paths}
    if '-a' in args:
        options['show_all'] = True
    if '-t' in args:
        options['success_rate_threshold'] = float(args[args.index('-t') + 1])
    if '-s' in args:
        options['just_show_statistics'] = True
    if '-u' in args:
        options['just_show_uncertainties'] = True
    return options

if __name__ == '__main__':
    options = get_options()
    buddy = StudyBuddy(**options)
    buddy.study()
