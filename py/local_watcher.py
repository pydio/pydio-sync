import time
import threading
import logging

from watchdog.events import DirCreatedEvent, DirDeletedEvent, DirMovedEvent, \
    FileCreatedEvent, FileDeletedEvent, FileMovedEvent
from watchdog.observers import Observer
from watchdog.utils.dirsnapshot import DirectorySnapshot, DirectorySnapshotDiff

from py.localdb import SqlEventHandler, SqlSnapshot

# -*- coding: utf-8 -*-


class LocalWatcher(threading.Thread):

    def __init__(self, local_path, includes, excludes):
        threading.Thread.__init__(self)
        self.basepath = unicode(local_path)
        self.observer = None
        self.includes = includes
        self.excludes = excludes

    def stop(self):
        self.observer.stop()

    def run(self):
        event_handler = SqlEventHandler(includes=self.includes, excludes=self.excludes, basepath=self.basepath)

        logging.info('Scanning for changes since last application launch')
        previous_snapshot = SqlSnapshot(self.basepath)
        snapshot = DirectorySnapshot(self.basepath, recursive=True)
        diff = DirectorySnapshotDiff(previous_snapshot, snapshot)
        for path in diff.dirs_created:
            event_handler.on_created(DirCreatedEvent(path))
        for path in diff.files_created:
            event_handler.on_created(FileCreatedEvent(path))
        for path in diff.dirs_moved:
            event_handler.on_moved(DirMovedEvent(path[0], path[1]))
        for path in diff.files_moved:
            event_handler.on_moved(FileMovedEvent(path[0], path[1]))
        for path in diff.files_deleted:
            event_handler.on_deleted(FileDeletedEvent(path))
        for path in diff.dirs_deleted:
            event_handler.on_deleted(DirDeletedEvent(path))

        logging.info('Starting permanent monitor')
        self.observer = Observer()
        self.observer.schedule(event_handler, self.basepath, recursive=True)
        self.observer.start()
        while True:
            time.sleep(1)
        self.observer.join()

