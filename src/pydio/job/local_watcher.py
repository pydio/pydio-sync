#
# Copyright 2007-2014 Charles du Jeu - Abstrium SAS <team (at) pyd.io>
# This file is part of Pydio.
#
#  Pydio is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#
#  Pydio is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with Pydio.  If not, see <http://www.gnu.org/licenses/>.
#
#  The latest code can be found at <http://pyd.io/>.
#
import threading
import logging
import stat
import sys
import os
import time

from watchdog.events import DirCreatedEvent, DirDeletedEvent, DirMovedEvent, \
    FileCreatedEvent, FileDeletedEvent, FileMovedEvent, FileModifiedEvent
from watchdog.observers import Observer
from watchdog.utils import platform
if platform.is_linux():
    from watchdog.observers.polling import PollingObserver as Observer
from watchdog.utils.dirsnapshot import DirectorySnapshot, DirectorySnapshotDiff

from pydio.job.localdb import SqlEventHandler, SqlSnapshot
from pydio.utils.pydio_profiler import pydio_profile

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
        for path, stat_info in dirsnap._stat_info.items():
            if path in ref_dirsnap.stat_snapshot:
                ref_stat_info = ref_dirsnap.stat_info(path)
                if long(stat_info.st_mtime) != long(ref_stat_info.st_mtime):
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
    def __init__(self, local_path, data_path, event_handler):
        threading.Thread.__init__(self)
        self.basepath = unicode(local_path)
        self.observer = None
        self.job_data_path = data_path
        self.interrupt = False
        self.event_handler = event_handler

    @pydio_profile
    def check_from_snapshot(self, sub_folder=None, state_callback=(lambda status: None)):
        from pydio.utils import i18n
        _ = i18n.language.ugettext

        logging.info('Scanning for changes since last application launch')
        if (not sub_folder and os.path.exists(self.basepath)) or (sub_folder and os.path.exists(self.basepath + sub_folder)):
            previous_snapshot = SqlSnapshot(self.basepath, self.job_data_path, sub_folder)
            if sub_folder:
                local_path = self.basepath + os.path.normpath(sub_folder)
            else:
                local_path = self.basepath
            state_callback(status=_('Walking through your local folder, please wait...'))

            def listdir(dir_path):
                try:
                    return os.listdir(dir_path)
                except OSError as o:
                    logging.error(o)
                    return []

            snapshot = DirectorySnapshot(local_path, recursive=True, listdir=listdir)
            diff = SnapshotDiffStart(previous_snapshot, snapshot)
            state_callback(status=_('Detected %i local changes...') % (len(diff.dirs_created) + len(diff.files_created)
                                                                       + len(diff.dirs_moved) + len(diff.dirs_deleted)
                                                                       + len(diff.files_moved) +
                                                                       len(diff.files_modified) +
                                                                       len(diff.files_deleted)))

            self.event_handler.begin_transaction()

            for path in diff.dirs_created:
                if self.interrupt:
                    return
                self.event_handler.on_created(DirCreatedEvent(path))
            for path in diff.files_created:
                if self.interrupt:
                    return
                self.event_handler.on_created(FileCreatedEvent(path))

            for path in diff.dirs_moved:
                if self.interrupt:
                    return
                self.event_handler.on_moved(DirMovedEvent(path[0], path[1]))
            for path in diff.files_moved:
                if self.interrupt:
                    return
                self.event_handler.on_moved(FileMovedEvent(path[0], path[1]))
            for path in diff.files_modified:
                if self.interrupt:
                    return
                self.event_handler.on_modified(FileModifiedEvent(path))
            for path in diff.files_deleted:
                if self.interrupt:
                    return
                self.event_handler.on_deleted(FileDeletedEvent(path))
            for path in diff.dirs_deleted:
                if self.interrupt:
                    return
                self.event_handler.on_deleted(DirDeletedEvent(path))

            self.event_handler.end_transaction()

    @pydio_profile
    def stop(self):
        self.interrupt = True
        if self.observer:
            logging.debug("Stopping: %s" % self.observer)
            try:
                self.observer.stop()
            except Exception:
                logging.error("Error while stopping watchdog thread!")

    @pydio_profile
    def run(self):
        if not os.path.exists(self.basepath):
            logging.error('Cannot start monitor on non-existing path ' + self.basepath)
            return

        logging.info('Starting permanent monitor')
        self.observer = Observer()
        self.observer.schedule(self.event_handler, self.basepath, recursive=True)
        self.observer.start()
        self.observer.join()

