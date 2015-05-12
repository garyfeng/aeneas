#!/usr/bin/env python
# coding=utf-8

"""
Analyze a given container and build the corresponding job.
"""

import os
import re

import aeneas.globalconstants as gc
import aeneas.globalfunctions as gf
from aeneas.container import Container
from aeneas.hierarchytype import HierarchyType
from aeneas.job import Job, JobConfiguration
from aeneas.language import Language
from aeneas.logger import Logger
from aeneas.syncmap import SyncMapFormat
from aeneas.task import Task, TaskConfiguration
from aeneas.textfile import TextFileFormat

__author__ = "Alberto Pettarin"
__copyright__ = """
    Copyright 2012-2013, Alberto Pettarin (www.albertopettarin.it)
    Copyright 2013-2015, ReadBeyond Srl (www.readbeyond.it)
    """
__license__ = "GNU AGPL v3"
__version__ = "1.0.0"
__email__ = "aeneas@readbeyond.it"
__status__ = "Production"

class AnalyzeContainer(object):
    """
    Analyze a given container and build the corresponding job.

    :param container: the container to be analyzed
    :type  container: :class:`aeneas.container.Container`
    :param logger: the logger object
    :type  logger: :class:`aeneas.logger.Logger`
    """

    TAG = "AnalyzeContainer"

    def __init__(self, container, logger=None):
        self.logger = logger
        if self.logger == None:
            self.logger = Logger()
        self.container = container

    def analyze(self):
        """
        Analyze the given container and
        return the corresponding job object.

        On error, it will return ``None``.

        :rtype: :class:`aeneas.job.Job`
        """
        if self.container.has_config_xml:
            self._log("Analyzing container with XML config file")
            return self._analyze_xml_config(config_contents=None)
        elif self.container.has_config_txt:
            self._log("Analyzing container with TXT config file")
            return self._analyze_txt_config(config_string=None)
        else:
            self._log("No configuration file in this container, returning None")
            return None

    def analyze_from_wizard(self, config_string):
        """
        Analyze the given container using the given config string
        and return the corresponding job.

        On error, it will return ``None``.

        :param config_string: the configuration string generated by the wizard
        :type  config_string: string
        :rtype: :class:`aeneas.job.Job`
        """
        self._log("Analyzing container with config string from wizard")
        return self._analyze_txt_config(config_string=config_string)

    def _log(self, message, severity=Logger.DEBUG):
        """ Log """
        self.logger.log(message, severity, self.TAG)

    def _analyze_txt_config(self, config_string=None):
        """
        Analyze the given container and return the corresponding job.

        If ``config_string`` is ``None``,
        try reading it from the TXT config file inside the container.

        :param config_string: the configuration string
        :type  config_string: string
        :rtype: :class:`aeneas.job.Job`
        """
        # TODO break this function down into smaller functions
        self._log("Analyzing container with TXT config string")

        if config_string == None:
            self._log("Analyzing container with TXT config file")
            config_entry = self.container.entry_config_txt
            self._log("Found TXT config entry '%s'" % config_entry)
            config_dir = os.path.dirname(config_entry)
            self._log("Directory of TXT config entry: '%s'" % config_dir)
            self._log("Reading TXT config entry: '%s'" % config_entry)
            config_contents = self.container.read_entry(config_entry)
            #self._log("Removing BOM")
            #config_contents = gf.remove_bom(config_contents)
            self._log("Converting config contents to config string")
            config_string = gf.config_txt_to_string(config_contents)
        else:
            self._log("Analyzing container with TXT config string '%s'" % config_string)
            config_dir = ""
            #self._log("Removing BOM")
            #config_string = gf.remove_bom(config_string)

        # create the Job object to be returned
        self._log("Creating the Job object")
        job = Job(config_string)

        # get the entries in this container
        self._log("Getting entries")
        entries = self.container.entries()

        # convert the config string to dict
        self._log("Converting config string into config dict")
        parameters = gf.config_string_to_dict(config_string)

        # compute the root directory for the task assets
        self._log("Calculating the path of the tasks root directory")
        tasks_root_directory = gf.norm_join(
            config_dir,
            parameters[gc.PPN_JOB_IS_HIERARCHY_PREFIX]
        )
        self._log("Path of the tasks root directory: '%s'" % tasks_root_directory)

        # compute the root directory for the sync map files
        self._log("Calculating the path of the sync map root directory")
        sync_map_root_directory = gf.norm_join(
            config_dir,
            parameters[gc.PPN_JOB_OS_HIERARCHY_PREFIX]
        )
        job_os_hierarchy_type = parameters[gc.PPN_JOB_OS_HIERARCHY_TYPE]
        self._log("Path of the sync map root directory: '%s'" % sync_map_root_directory)

        # prepare relative path and file name regex for text and audio files
        text_file_relative_path = parameters[gc.PPN_JOB_IS_TEXT_FILE_RELATIVE_PATH]
        self._log("Relative path for text file: '%s'" % text_file_relative_path)
        text_file_name_regex = re.compile(r"" + parameters[gc.PPN_JOB_IS_TEXT_FILE_NAME_REGEX])
        self._log("Regex for text file: '%s'" % parameters[gc.PPN_JOB_IS_TEXT_FILE_NAME_REGEX])
        audio_file_relative_path = parameters[gc.PPN_JOB_IS_AUDIO_FILE_RELATIVE_PATH]
        self._log("Relative path for audio file: '%s'" % audio_file_relative_path)
        audio_file_name_regex = re.compile(r"" + parameters[gc.PPN_JOB_IS_AUDIO_FILE_NAME_REGEX])
        self._log("Regex for audio file: '%s'" % parameters[gc.PPN_JOB_IS_AUDIO_FILE_NAME_REGEX])

        # flat hierarchy
        if parameters[gc.PPN_JOB_IS_HIERARCHY_TYPE] == HierarchyType.FLAT:
            self._log("Looking for text/audio pairs in flat hierarchy")
            text_files = self._find_files(
                entries,
                tasks_root_directory,
                text_file_relative_path,
                text_file_name_regex
            )
            self._log("Found text files: '%s'" % str(text_files))
            audio_files = self._find_files(
                entries,
                tasks_root_directory,
                audio_file_relative_path,
                audio_file_name_regex
            )
            self._log("Found audio files: '%s'" % str(audio_files))

            self._log("Matching files in flat hierarchy...")
            matched_tasks = self._match_files_flat_hierarchy(
                text_files,
                audio_files
            )
            self._log("Matching files in flat hierarchy... done")

            for task_info in matched_tasks:
                self._log("Creating task: '%s'" % str(task_info))
                task = self._create_task(
                    task_info,
                    config_string,
                    sync_map_root_directory,
                    job_os_hierarchy_type
                )
                job.add_task(task)

        # paged hierarchy
        if parameters[gc.PPN_JOB_IS_HIERARCHY_TYPE] == HierarchyType.PAGED:
            self._log("Looking for text/audio pairs in paged hierarchy")
            # find all subdirectories of tasks_root_directory
            # that match gc.PPN_JOB_IS_TASK_DIRECTORY_NAME_REGEX
            matched_directories = self._match_directories(
                entries,
                tasks_root_directory,
                parameters[gc.PPN_JOB_IS_TASK_DIRECTORY_NAME_REGEX]
            )
            for matched_directory in matched_directories:
                # rebuild the full path
                matched_directory_full_path = gf.norm_join(
                    tasks_root_directory,
                    matched_directory
                )
                self._log("Looking for text/audio pairs in directory '%s'" % matched_directory_full_path)

                # look for text and audio files there
                text_files = self._find_files(
                    entries,
                    matched_directory_full_path,
                    text_file_relative_path,
                    text_file_name_regex
                )
                self._log("Found text files: '%s'" % str(text_files))
                audio_files = self._find_files(
                    entries,
                    matched_directory_full_path,
                    audio_file_relative_path,
                    audio_file_name_regex
                )
                self._log("Found audio files: '%s'" % str(audio_files))

                # if we have found exactly one text and one audio file,
                # create a Task
                if (len(text_files) == 1) and (len(audio_files) == 1):
                    self._log("Exactly one text file and one audio file in '%s'" % matched_directory)
                    task_info = [
                        matched_directory,
                        text_files[0],
                        audio_files[0]
                    ]
                    self._log("Creating task: '%s'" % str(task_info))
                    task = self._create_task(
                        task_info,
                        config_string,
                        sync_map_root_directory,
                        job_os_hierarchy_type
                    )
                    job.add_task(task)
                elif len(text_files) > 1:
                    self._log("More than one text file in '%s'" % matched_directory)
                elif len(audio_files) > 1:
                    self._log("More than one audio file in '%s'" % matched_directory)
                else:
                    self._log("No text nor audio file in '%s'" % matched_directory)

        # return the Job
        return job

    def _analyze_xml_config(self, config_contents=None):
        """
        Analyze the given container and return the corresponding job.

        If ``config_contents`` is ``None``,
        try reading it from the XML config file inside the container.

        :param config_contents: the contents of the XML config file
        :type  config_contents: string
        :rtype: :class:`aeneas.job.Job`
        """
        # TODO break this function down into smaller functions
        self._log("Analyzing container with XML config string")

        if config_contents == None:
            self._log("Analyzing container with XML config file")
            config_entry = self.container.entry_config_xml
            self._log("Found XML config entry '%s'" % config_entry)
            config_dir = os.path.dirname(config_entry)
            self._log("Directory of XML config entry: '%s'" % config_dir)
            self._log("Reading XML config entry: '%s'" % config_entry)
            config_contents = self.container.read_entry(config_entry)
        else:
            self._log("Analyzing container with XML config contents")
            config_dir = ""

        # remove BOM
        #self._log("Removing BOM")
        #config_contents = gf.remove_bom(config_contents)

        # get the job parameters and tasks parameters
        self._log("Converting config contents into job config dict")
        job_parameters = gf.config_xml_to_dict(
            config_contents,
            result=None,
            parse_job=True
        )
        self._log("Converting config contents into tasks config dict")
        tasks_parameters = gf.config_xml_to_dict(
            config_contents,
            result=None,
            parse_job=False
        )

        # compute the root directory for the sync map files
        self._log("Calculating the path of the sync map root directory")
        sync_map_root_directory = gf.norm_join(
            config_dir,
            job_parameters[gc.PPN_JOB_OS_HIERARCHY_PREFIX]
        )
        job_os_hierarchy_type = job_parameters[gc.PPN_JOB_OS_HIERARCHY_TYPE]
        self._log("Path of the sync map root directory: '%s'" % sync_map_root_directory)

        # create the Job object to be returned
        self._log("Converting job config dict into job config string")
        config_string = gf.config_dict_to_string(job_parameters)
        job = Job(config_string)

        # create the Task objects
        for task_parameters in tasks_parameters:
            self._log("Converting task config dict into task config string")
            config_string = gf.config_dict_to_string(task_parameters)
            self._log("Creating task with config string '%s'" % config_string)
            try:
                custom_id = task_parameters[gc.PPN_TASK_CUSTOM_ID]
            except KeyError:
                custom_id = ""
            task_info = [
                custom_id,
                gf.norm_join(
                    config_dir,
                    task_parameters[gc.PPN_TASK_IS_TEXT_FILE_XML]
                ),
                gf.norm_join(
                    config_dir,
                    task_parameters[gc.PPN_TASK_IS_AUDIO_FILE_XML]
                )
            ]
            self._log("Creating task: '%s'" % str(task_info))
            task = self._create_task(
                task_info,
                config_string,
                sync_map_root_directory,
                job_os_hierarchy_type
            )
            job.add_task(task)

        # return the Job
        return job

    def _create_task(
            self,
            task_info,
            config_string,
            sync_map_root_directory,
            job_os_hierarchy_type
        ):
        """
        Create a task object from

        1. the ``task_info`` found analyzing the container entries, and
        2. the given ``config_string``.

        :param task_info: the task information: ``[prefix, text_path, audio_path]``
        :type  task_info: list of strings
        :param config_string: the configuration string
        :type  config_string: string
        :param sync_map_root_directory: the root directory for the sync map files
        :type  sync_map_root_directory: string (path)
        :param job_os_hierarchy_type: type of job output hierarchy
        :type  job_os_hierarchy_type: :class:`aeneas.hierarchytype.HierarchyType`
        :rtype: :class:`aeneas.task.Task`
        """
        self._log("Converting config string to config dict")
        parameters = gf.config_string_to_dict(config_string)
        self._log("Creating task")
        task = Task(config_string)
        task.configuration.description = "Task %s" % task_info[0]
        self._log("Task description: %s" % task.configuration.description)
        try:
            task.configuration.language = parameters[gc.PPN_TASK_LANGUAGE]
            self._log("Set language from task: '%s'" % task.configuration.language)
        except KeyError:
            task.configuration.language = parameters[gc.PPN_JOB_LANGUAGE]
            self._log("Set language from job: '%s'" % task.configuration.language)
        custom_id = task_info[0]
        task.configuration.custom_id = custom_id
        self._log("Task custom_id: %s" % task.configuration.custom_id)
        task.text_file_path = task_info[1]
        self._log("Task text file path: %s" % task.text_file_path)
        task.audio_file_path = task_info[2]
        self._log("Task audio file path: %s" % task.audio_file_path)
        task.sync_map_file_path = self._compute_sync_map_file_path(
            sync_map_root_directory,
            job_os_hierarchy_type,
            custom_id,
            task.configuration.os_file_name
        )
        self._log("Task sync map file path: %s" % task.sync_map_file_path)

        self._log("Replacing placeholder in os_file_smil_audio_ref")
        task.configuration.os_file_smil_audio_ref = self._replace_placeholder(
            task.configuration.os_file_smil_audio_ref,
            custom_id
        )
        self._log("Replacing placeholder in os_file_smil_page_ref")
        task.configuration.os_file_smil_page_ref = self._replace_placeholder(
            task.configuration.os_file_smil_page_ref,
            custom_id
        )
        self._log("Returning task")
        return task

    def _replace_placeholder(self, string, custom_id):
        """
        Replace the prefix placeholder
        :class:`aeneas.globalconstants.PPV_OS_TASK_PREFIX`
        with ``custom_id`` and return the resulting string.

        :rtype: string
        """
        if string == None:
            return None
        self._log("Replacing '%s' with '%s' in '%s'" % (gc.PPV_OS_TASK_PREFIX, custom_id, string))
        return string.replace(gc.PPV_OS_TASK_PREFIX, custom_id)

    def _compute_sync_map_file_path(
            self,
            root,
            hierarchy_type,
            custom_id,
            file_name
        ):
        """
        Compute the sync map file path inside the output container.

        :param root: the root of the sync map files inside the container
        :type  root: string (path)
        :param job_os_hierarchy_type: type of job output hierarchy
        :type  job_os_hierarchy_type: :class:`aeneas.hierarchytype.HierarchyType`
        :param custom_id: the task custom id (flat) or
                          page directory name (paged)
        :type  custom_id: string
        :param file_name: the output file name for the sync map
        :type  file_name: string
        :rtype: string (path)
        """
        prefix = root
        if hierarchy_type == HierarchyType.PAGED:
            prefix = gf.norm_join(prefix, custom_id)
        file_name_joined = gf.norm_join(prefix, file_name)
        return self._replace_placeholder(file_name_joined, custom_id)

    def _find_files(self, entries, root, relative_path, file_name_regex):
        """
        Return the elements in entries that

        1. are in ``root/relative_path``, and
        2. match ``file_name_regex``.

        :param entries: the list of entries (file paths) in the container
        :type  entries: list of strings (path)
        :param root: the root directory of the container
        :type  root: string (path)
        :param relative_path: the relative path in which we must search
        :type  relative_path: string (path)
        :param file_name_regex: the regex matching the desired file names
        :type  file_name_regex: regex
        :rtype: list of strings (path)
        """
        self._log("Finding files within root: '%s'" % root)
        target = root
        if relative_path != None:
            self._log("Joining relative path: '%s'" % relative_path)
            target = gf.norm_join(root, relative_path)
        self._log("Finding files within target: '%s'" % target)
        files = []
        target_len = len(target)
        for entry in entries:
            if entry.startswith(target):
                self._log("Examining entry: '%s'" % entry)
                entry_suffix = entry[target_len + 1:]
                self._log("Examining entry suffix: '%s'" % entry_suffix)
                if re.search(file_name_regex, entry_suffix) != None:
                    self._log("Match: '%s'" % entry)
                    files.append(entry)
                else:
                    self._log("No match: '%s'" % entry)
        return sorted(files)

    def _match_files_flat_hierarchy(self, text_files, audio_files):
        """
        Match audio and text files in flat hierarchies.

        Two files match if their names,
        once removed the file extension,
        are the same.

        Examples: ::

            foo/text/a.txt foo/audio/a.mp3 => match: ["a", "foo/text/a.txt", "foo/audio/a.mp3"]
            foo/text/a.txt foo/audio/b.mp3 => no match
            foo/res/c.txt  foo/res/c.mp3   => match: ["c", "foo/res/c.txt", "foo/res/c.mp3"]
            foo/res/d.txt  foo/res/e.mp3   => no match

        :param text_files: the entries corresponding to text files
        :type  text_files: list of strings (path)
        :param audio_files: the entries corresponding to audio files
        :type  audio_files: list of strings (path)
        :rtype: list of lists (see above)
        """
        self._log("Matching files in flat hierarchy")
        self._log("Text files: '%s'" % text_files)
        self._log("Audio files: '%s'" % audio_files)
        d_text = dict()
        d_audio = dict()
        for text_file in text_files:
            text_file_no_ext = gf.file_name_without_extension(text_file)
            d_text[text_file_no_ext] = text_file
            self._log("Added text file '%s' to key '%s'" % (text_file, text_file_no_ext))
        for audio_file in audio_files:
            audio_file_no_ext = gf.file_name_without_extension(audio_file)
            d_audio[audio_file_no_ext] = audio_file
            self._log("Added audio file '%s' to key '%s'" % (audio_file, audio_file_no_ext))
        tasks = []
        for key in d_text.keys():
            self._log("Examining text key '%s'" % key)
            if key in d_audio:
                self._log("Key '%s' is also in audio" % key)
                tasks.append([key, d_text[key], d_audio[key]])
                self._log("Added pair ('%s', '%s')" % (d_text[key], d_audio[key]))
        return tasks

    def _match_directories(self, entries, root, regex_string):
        """
        Match directory names in paged hierarchies.

        Example: ::

            root = /foo/bar
            regex_string = [0-9]+

            /foo/bar/
                     1/
                       bar
                       baz
                     2/
                       bar
                     3/
                       foo

            => ["/foo/bar/1", "/foo/bar/2", "/foo/bar/3"]

        :param entries: the list of entries (paths) of a container
        :type  entries: list of strings (paths)
        :param root: the root directory to search within
        :type  root: string (path)
        :param regex_string: regex string to match directory names
        :type  regex_string: string
        :rtype: list of matched directories
        """
        self._log("Matching directory names in paged hierarchy")
        self._log("Matching within '%s'" % root)
        self._log("Matching regex '%s'" % regex_string)
        regex = re.compile(r"" + regex_string)
        directories = set()
        root_len = len(root)
        for entry in entries:
            # look only inside root dir
            if entry.startswith(root):
                self._log("Examining '%s'" % entry)
                # remove common prefix root/
                entry = entry[root_len + 1:]
                # split path
                entry_splitted = entry.split(os.sep)
                # match regex
                if ((len(entry_splitted) >= 2) and
                        (re.match(regex, entry_splitted[0]) != None)):
                    directories.add(entry_splitted[0])
                    self._log("Match: '%s'" % entry_splitted[0])
                else:
                    self._log("No match: '%s'" % entry)
        return sorted(directories)


