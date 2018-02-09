

import random
import sys



class StudyBuddy(object):

    def __init__(self, file_path):
        self.file_path = file_path
        self._set_lines()
        self._set_points()

    def _set_lines(self):
        with open(self.file_path,'r') as f:
            unformatted_lines = f.read().splitlines()
        self.lines = []
        for line in unformatted_lines:
            if len(line) > 1:
                self.lines.append(line.strip())

    def _set_points(self):
        self.points = []
        self.new_point = {}
        for line in self.lines:
            if 'question' not in self.new_point:
                self.new_point = {'question': line}
            else:
                self.new_point['answer'] = line
                self.points.append(self.new_point)
                self.new_point = {}
        random.shuffle(self.points)

    def study(self):
        for point in self.points:
            print '\n'
            print point['question']
            raw_input()
            print point['answer']
            raw_input()



if __name__ == '__main__':
    file_path = sys.argv[1]
    buddy = StudyBuddy(file_path)
    buddy.study()
