#
#  Copyright 2007-2014 Charles du Jeu - Abstrium SAS <team (at) pyd.io>
#  This file is part of Pydio.
#
#  Pydio is free software: you can redistribute it and/or modify
#  it under the terms of the GNU Affero General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#
#  Pydio is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU Affero General Public License for more details.
#
#  You should have received a copy of the GNU Affero General Public License
#  along with Pydio.  If not, see <http://www.gnu.org/licenses/>.
#
#  The latest code can be found at <http://pyd.io/>.
#


import time
import threading
import logging
from pydio.job import stop_on_keyboard_interrupt
import stat
import sys
import os

from watchdog.events import DirCreatedEvent, DirDeletedEvent, DirMovedEvent, \
    FileCreatedEvent, FileDeletedEvent, FileMovedEvent, FileModifiedEvent
from watchdog.observers import Observer
from watchdog.utils.dirsnapshot import DirectorySnapshot, DirectorySnapshotDiff

from pydio.job.localdb import SqlEventHandler, SqlSnapshot


# -*- coding: utf-8 -*-
class SnapshotDiffStart(DirectorySnapshotDiff):

  def __init__(self, ref_dirsnap, dirsnap):
    """
    """
    self._files_deleted = list()
    self._files_modified = list()
    self._files_created = list()
    self._files_moved = list()

    self._dirs_modified = list()
    self._dirs_moved = list()
    self._dirs_deleted = list()
    self._dirs_created = list()

    # Detect all the modifications.
    for path, stat_info in dirsnap.stat_snapshot.items():
      if path in ref_dirsnap.stat_snapshot:
        ref_stat_info = ref_dirsnap.stat_info(path)
        if stat_info.st_mtime != ref_stat_info.st_mtime:
          if stat.S_ISDIR(stat_info.st_mode):
            self._dirs_modified.append(path)
          else:
            self._files_modified.append(path)

    paths_deleted = set(ref_dirsnap.paths) - set(dirsnap.paths)
    paths_created = set(dirsnap.paths) - set(ref_dirsnap.paths)

    # Detect all the moves/renames.
    # Doesn't work on Windows, so exlude on Windows.
    if not sys.platform.startswith('win'):
      for created_path in set(paths_created).copy():
        created_stat_info = dirsnap.stat_info(created_path)
        for deleted_path in paths_deleted.copy():
          deleted_stat_info = ref_dirsnap.stat_info(deleted_path)
          if created_stat_info.st_ino == deleted_stat_info.st_ino:
            paths_deleted.remove(deleted_path)
            paths_created.remove(created_path)
            if stat.S_ISDIR(created_stat_info.st_mode):
              self._dirs_moved.append((deleted_path, created_path))
            else:
              self._files_moved.append((deleted_path, created_path))

    # Now that we have renames out of the way, enlist the deleted and
    # created files/directories.
    for path in paths_deleted:
      stat_info = ref_dirsnap.stat_info(path)
      if stat.S_ISDIR(stat_info.st_mode):
        self._dirs_deleted.append(path)
      else:
        self._files_deleted.append(path)

    for path in paths_created:
      stat_info = dirsnap.stat_info(path)
      if stat.S_ISDIR(stat_info.st_mode):
        self._dirs_created.append(path)
      else:
        self._files_created.append(path)



class LocalWatcher(threading.Thread):

    def __init__(self, local_path, includes, excludes, data_path):
        threading.Thread.__init__(self)
        self.basepath = unicode(local_path)
        self.observer = None
        self.includes = includes
        self.excludes = excludes

        self.event_handler = SqlEventHandler(includes=self.includes, excludes=self.excludes, basepath=self.basepath, job_data_path=data_path)

        logging.info('Scanning for changes since last application launch')
        if os.path.exists(self.basepath):
            previous_snapshot = SqlSnapshot(self.basepath, data_path)
            snapshot = DirectorySnapshot(self.basepath, recursive=True)
            diff = SnapshotDiffStart(previous_snapshot, snapshot)
            for path in diff.dirs_created:
                self.event_handler.on_created(DirCreatedEvent(path))
            for path in diff.files_created:
                self.event_handler.on_created(FileCreatedEvent(path))
            for path in diff.dirs_moved:
                self.event_handler.on_moved(DirMovedEvent(path[0], path[1]))
            for path in diff.files_moved:
                self.event_handler.on_moved(FileMovedEvent(path[0], path[1]))
            for path in diff.files_modified:
                self.event_handler.on_modified(FileModifiedEvent(path))
            for path in diff.files_deleted:
                self.event_handler.on_deleted(FileDeletedEvent(path))
            for path in diff.dirs_deleted:
                self.event_handler.on_deleted(DirDeletedEvent(path))

    def stop(self):
        logging.debug("Stopping: %s" % self.observer)
        self.observer.stop()

    @stop_on_keyboard_interrupt
    def run(self):

        logging.info('Starting permanent monitor')
        self.observer = Observer()
        self.observer.schedule(self.event_handler, self.basepath, recursive=True)
        self.observer.start()
        # while True:
        #     time.sleep(1)
        self.observer.join()

