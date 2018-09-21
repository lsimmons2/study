TODO: remove ticks from keyboard glyphs
<h1>My Study Program</h1>

This is a program I wrote to help me study notes I take in a flash-card manner.

<h3>Usage</h3>

The program works with files of notes organized in the following way:

- each note is represented as a question and an answer
- each question is on its own line and ends with a `?`
- the answer to each question is on the line below the question

For example:

```
what is bro?
bro!

what is brah?
brah!
```

To use:

1) call the program on the file: `$study.py file_to_study.txt`

2) you will be shown a question

2) try to answer the question as you would study a flash-card

3) hit <kbd>Enter</kbd>

4) you will be shown the answer

5) hit <kbd>y</kbd> or <kbd>c</kbd> if you got it right or <kbd>n</kbd> or <kbd>i</kbd> if you didn't, then <kbd>Enter</kbd>

6) program will save whether or not you got the question right in a metadata file - ids will be appended to the end of each question line to correlate with metadata file
 
7) next time you study the same file, you will only be shown the questions that the program determines you don't know [well enough](#choosing_what_questions_to_study)

 
<h3>Choosing what files to study</h3>

You can call the program on any number of files - `$study.py file_to_study.txt another_file_to_study.txt` - or directories - `$study.py file_to_study.txt dir_to_study/` - and it will group the specified files and the files in the directories and quiz you on all of them at the same time.

If calling on a directory, the only files inside the directory that will be studied will be those that have the "shebang" `*study` as the first non-empty line in the file.


<h3 name="choosing_what_questions_to_study">Choosing what questions to study</h3>

You can specify a "threshold" of what questions to study with the `-t` flag. The threshold is the percentage of previous answers to a question that were correct answers under which a question needs to fall to be shown to you.

For example: you have two questions, question A and question B, and you have answered them both 5 times. You answered question A correctly 3 out of those 5 times and question B 2 out of those 5 times. If you then call the program with `-t .5` question B will be shown to you (it has a `0.4` success rate) but question A will not be (it has a `0.6` success rate). The threshold is `0.8` by default.

If you pass the `-a` flag then "all" questions will be shown regardless of your previous success rate with them or the threshold.

A question will always be shown if it has been answered less than 3 times.


<h3>Other features</h3>

You can use images as questions or answers by using the file name of an image as the question or answer line and making sure the images are in a directory specified by the `STUDY_IMAGES_DIR` environmental variable. You also will need to be on a Linux system where the bash command `gnome-open` will open image files.

You can keep "uncertainties" in the files - questions you have that you don't yet have the answers to and therefore don't want to be quizzed on - by prepending the lines with a `*`. Call the program with the `-u` flag to just see the uncertainties in files.

You can see the number of successful answers for questions in files by passing the `-s` flag.

You can set the `STUDY_BASE_DIR` environmental variable and this directory will be searched for files (with the `*study` shebang) to study if no files or directories are passed as arguments when calling the program.

You can set the `METADATA_FILE_PATH` if you want to specify where metadata file will be stored. If you don't set this variable the file will be called `.study_metadata.json` and will be in your home directory.
