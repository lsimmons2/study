
import sys
import re
import json
import subprocess
import os
import signal
import collections
import fileinput



class StudyBuddy(object):


    def __init__(self, study_file_paths=None, show_all=False, success_rate_threshold=0.8, just_show_statistics=False, just_show_uncertainties=False):
        self.study_file_paths = study_file_paths
        self.show_all = show_all
        self.success_rate_threshold = success_rate_threshold
        self.just_show_statistics = just_show_statistics
        self.just_show_uncertainties = just_show_uncertainties
        self.files = self._create_files()
        self._update_metadata_file_and_study_files_with_new_point_ids()
        self._filter_and_sort_points_to_study()


    def _get_highest_point_id_in_metadata_file(self):
        point_ids = [ int(id) for id in metadata_client.get_all_points_metadata() ]
        try:
            highest_current_point_id = sorted(point_ids)[-1]
            return highest_current_point_id
        except IndexError:
            return 0


    def _create_files(self):
        return [ File(file_path) for file_path in self.study_file_paths ]


    def _update_metadata_file_and_study_files_with_new_point_ids(self):
        new_points = []
        highest_point_id = self._get_highest_point_id_in_metadata_file()
        for file in self.files:
            # give ids to all new points in files
            new_points_in_file = []
            for point in file.points:
                if point.is_new:
                    point.id = highest_point_id + 1
                    highest_point_id = point.id
                    new_points_in_file.append(point)
            # add the new ids to end of question lines in study files
            for new_point in new_points_in_file:
                for line in fileinput.input(file.path, inplace=True):
                    if fileinput.filelineno() == new_point.line_no_in_file:
                        line_text = '%s %d\n' % (new_point.question, new_point.id)
                    else:
                        line_text = line
                    sys.stdout.write(line_text) # stdout written to file
            new_points = new_points + new_points_in_file
        metadata_client.update_points_metadata(new_points)


    def _filter_and_sort_points_to_study(self):
        for file in self.files:
            file.points_to_study = [ p for p in file.points if self._should_study_point(p) ]
            file.points_to_study.sort(key=lambda x: (x.total_attempt_count, x.success_rate))

            
    def _should_study_point(self, point):
        if point.is_hidden and not self.show_all:
            return False
        if point.total_attempt_count < 3:
            return True
        if point.success_rate > self.success_rate_threshold:
            return False
        return True


    def _show_all_point_stats(self):
        for file in self.files:
            file.print_path_header()
            for point in file.points:
                print '\n%s %s' % (point.question, point.id)
                print '%d / %d = %.2f' % (point.successful_attempt_count,
                                          point.total_attempt_count,
                                          point.success_rate)


    def _get_seen_points(self):
        seen_points = []
        for file in self.files:
            for point in file.points:
                if point.was_attempted or point.was_passed or point.was_marked_to_be_hidden:
                    seen_points.append(point)
        return seen_points


    def _show_study_session_stats(self):
        points_seen = self._get_seen_points()
        successful_attempt_count = 0
        pass_count = 0
        hidden_count = 0
        for point in points_seen:
            if point.was_attempted_successfully:
                successful_attempt_count += 1
            elif point.was_passed:
                pass_count += 1
            elif point.was_marked_to_be_hidden:
                hidden_count += 1
        total_attempt_count = len(points_seen) - pass_count
        stats_str = '\n%d points attempted, %d answered correctly.' % (total_attempt_count,
                                                                       successful_attempt_count)
        if pass_count:
            stats_str = '%s, %d passed.' % (stats_str[:-1], pass_count)
        if hidden_count:
            stats_str = '%s, %d hidden.' % (stats_str[:-1], hidden_count)
        print stats_str


    def _show_uncertainties(self):
        for file in self.files:
            if file.uncertainties:
                file.print_path_header()
            for uncertainty in file.uncertainties:
                print uncertainty.text


    def study(self):
        if self.just_show_statistics:
            return self._show_all_point_stats()
        if self.just_show_uncertainties:
            return self._show_uncertainties()
        try:
            for file in self.files:
                if file.points_to_study:
                    file.print_path_header()
                    for point in file.points_to_study:
                        point.study()
        except KeyboardInterrupt:
            print '\nExiting early'
        self._tear_down()
        self._show_study_session_stats()


    def _tear_down(self):
        # tearing down here and not in Point because saving each point in Point
        # wouldn't work (not all points were saved before program exited), also
        # reading and writing the metadata file in each point is inefficient
        seen_points = self._get_seen_points()
        metadata_client.update_points_metadata(seen_points)




class Point(object):


    default_metadata = {
        'total_attempt_count': 0,
        'successful_attempt_count': 0,
        'is_hidden': False
    }


    def __init__(self, question, answer_line, point_id, line_no_in_file):
        self.question = question
        self.answer = answer_line
        self.id = point_id
        self.line_no_in_file = line_no_in_file
        self.question_is_image = self._is_image_path(question)
        self.answer_is_image = self._is_image_path(answer_line)
        self._trim_question_line()
        self.is_new = self._determine_if_new()
        self._read_or_create_metadata_and_sync_to_metadata_file()
        self.success_rate = self._get_success_rate()
        self.images = []
        self.was_attempted = False
        self.was_attempted_successfully = False
        self.was_passed = False
        self.was_marked_to_be_hidden = False


    def __str__(self):
        if self.question_is_image:
            question_snippet = self.question
        else:
            question_snippet = '"%s...?"' % self.question[:25]
        return '<Point %d %s>' % (self.id, question_snippet)


    def _determine_if_new(self):
        return not bool(self.id)


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
        question_end_index = self.question.rfind('?')
        if self.question_is_image:
            # can't have point id or ? in an image path
            self.question = self.question[:question_end_index:]
        else:
            # don't store the id with the question text
            self.question = self.question[:question_end_index+1]


    def get_metadata(self):
        updated_metadata = {}
        for attr in self.default_metadata.keys():
            updated_metadata[attr] = getattr(self, attr)
        if self.was_attempted:
            updated_metadata['total_attempt_count'] += 1
        if self.was_attempted_successfully:
            updated_metadata['successful_attempt_count'] += 1
        if self.was_marked_to_be_hidden:
            updated_metadata['is_hidden'] = True
        return updated_metadata


    def close_images(self):
        for image in self.images:
            image.close()


    def _handle_response(self):
        response = raw_input()
        if response == 'h':
            self.was_marked_to_be_hidden = True
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


    def _read_or_create_metadata_and_sync_to_metadata_file(self):
        if not self.is_new:
            point_metadata = metadata_client.get_point_metadata(self.id)
        else:
            point_metadata = self.default_metadata
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



class Line(object):


    def __init__(self, text):
        self.text = text
        self.is_uncertainty = self._determine_if_uncertainty()
        self.is_question, self.point_id = self._determine_if_question_and_get_point_id()


    def _determine_if_uncertainty(self):
        return self.text.strip().startswith('*') and not self._is_study_shebang()


    def _is_study_shebang(self):
        return self.text.strip() == '*study'


    def _determine_if_question_and_get_point_id(self):
        if self.is_uncertainty:
            return False, None
        # TODO: combine this into one regex
        if self.text.strip().endswith('?'):
            return True, None
        try:
            point_id = int(re.search(r'\? (\d+)?$', self.text.strip()).groups(1)[0])
            return True, point_id
        except AttributeError:
            return False, None



class File(object):

    def __init__(self, path):
        self.path = path
        self.lines = self._create_line_objects()
        self.points = self._create_points()
        self.uncertainties = self._get_uncertainties()


    def print_path_header(self):
        print '\n\n*** %s ***' % self.path


    def _create_points(self):
        points = []
        for i, line in enumerate(self.lines):
            if line.is_question:
                question_line = line
                # answer line should be one after question line
                answer_line = self.lines[i+1]
                line_no = i + 1 # 0-indexed
                new_point = Point(question_line.text, answer_line.text, line.point_id, line_no)
                points.append(new_point)
        return points


    def _create_line_objects(self):
        with open(self.path, 'r') as f:
            return [ Line(line_text) for line_text in f.read().splitlines() ]


    def _get_uncertainties(self):
        return [ line for line in self.lines if line.is_uncertainty ]



class Config(object):

    IMAGES_DIR = os.getenv('STUDY_IMAGES_DIR')
    METADATA_FILE_PATH = os.getenv('METADATA_FILE_PATH')
    STUDY_BASE_DIR = os.getenv('STUDY_BASE_DIR')



class StudyFileSearcher(object):

    ''' searches through CLI args passed to program for paths of files to study '''

    def __init__(self, cli_args):
        self.cli_args = cli_args


    def is_study_file(self, file_path):
        ''' to be a study file, file has to be a .txt file and
        have a study "shebang" (*study) at the top of the file '''
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


    def get_study_file_paths_in_dir(self, directory, to_exclude_file_paths):
        study_file_paths = []
        for directory, sub_directories, files in os.walk(directory):
            for file_name in files:
                file_path = os.path.abspath(os.path.join(directory, file_name))
                if self.is_study_file(file_path):
                    study_file_paths.append(file_path)
        return [ fp for fp in study_file_paths if fp not in to_exclude_file_paths ]


    def search(self):
        to_exclude_arg_indeces = []
        to_exclude_file_paths = []
        for arg_index, arg in enumerate(self.cli_args):
            if arg == '-x':
                to_exclude_arg_indeces.append(arg_index)
                file_path = os.path.abspath(self.cli_args[arg_index+1])
                to_exclude_file_paths.append(file_path)
        for index in reversed(to_exclude_arg_indeces):
            del self.cli_args[index+1]
            del self.cli_args[index]
        study_file_paths = []
        for arg in self.cli_args:
            # if you explicitly specify a .txt file, then consider it a study file
            if arg.endswith('.txt'):
                file_path = os.path.abspath(arg)
                if file_path not in to_exclude_file_paths:
                    study_file_paths.append(file_path)
            # if you give a directory, recursively search it looking for files that
            # fit critera set in is_study_file()
            elif os.path.isdir(arg):
                study_file_paths = study_file_paths + get_study_file_paths_in_dir(arg, to_exclude_file_paths)
        if not study_file_paths:
            if Config.STUDY_BASE_DIR:
                print 'Searching for study files...'
                study_file_paths = self.get_study_file_paths_in_dir(Config.STUDY_BASE_DIR, to_exclude_file_paths)
            else:
                print 'Need to specify file or dir to study or set STUDY_BASE_DIR environmental variable.'
        all_file_paths = list(set(study_file_paths))
        file_log_str = 'file' if len(all_file_paths) == 1 else 'files'
        print '%d %s collected to study' % (len(all_file_paths), file_log_str)
        return all_file_paths
            


class MetadataClient(object):


    metadata_file_path = Config.METADATA_FILE_PATH


    def __init__(self):
        self._check_metadata_file()


    def get_point_metadata(self, point_id):
        all_points_metadata = self.get_all_points_metadata()
        try:
            return all_points_metadata[str(point_id)]
        except KeyError:
            # var for message so traceback isn't as crowded
            exception_message = 'Point with id %d not in study metadata file, make sure you\'re specifying the same METADATA_FILE_PATH as you did when you first studied that file that point %d is in.' % (point_id, point_id)
            raise Exception(exception_message)


    def get_all_points_metadata(self):
        with open(self.metadata_file_path, 'r') as f:
            return json.load(f, object_pairs_hook=collections.OrderedDict)


    def update_points_metadata(self, points_to_update):
        metadata = self.get_all_points_metadata()
        for point in points_to_update:
            metadata[str(point.id)] = point.get_metadata()
        with open(self.metadata_file_path, 'w') as f:
            json.dump(metadata, f, indent=2)


    def _check_metadata_file(self):
        try:
            if not self.metadata_file_path:
                home_dir = os.path.expanduser("~")
                self.metadata_file_path = "%s/.study_metadata.json" % home_dir
            with open(self.metadata_file_path, 'r') as f:
                json.load(f)
        except IOError:
            with open(self.metadata_file_path, 'w') as f:
                print 'Creating empty metadata file %s.' % self.metadata_file_path
                json.dump({}, f)
        except ValueError:
            raise Exception('Metadata file %s is messed up and isn\'t proper JSON.' % self.metadata_file_path)

metadata_client = MetadataClient()



def get_options():
    args = sys.argv[1:]
    study_file_searcher = StudyFileSearcher(args)
    options = {'study_file_paths': study_file_searcher.search()}
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
