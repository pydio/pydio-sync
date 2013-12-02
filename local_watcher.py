import time
import os
import threading
from watchdog.observers import Observer
from watchdog.utils.dirsnapshot import DirectorySnapshot, DirectorySnapshotDiff
import pickle
from localdb import SqlEventHandler
# -*- coding: utf-8 -*-

class LocalWatcher(threading.Thread):

    def __init__(self, local_path):
        threading.Thread.__init__(self)
        self.basepath = local_path

    def stop(self):
        self.observer.stop()

    def run(self):
        if os.path.exists("data/local_snapshot.p"):
            previous_snapshot = pickle.load(open("data/local_snapshot.p", "rb"))
            snapshot = DirectorySnapshot(self.basepath, recursive=True)
            diff = DirectorySnapshotDiff(previous_snapshot, snapshot)
            print diff.files_moved

        event_handler = SqlEventHandler(pattern='*', basepath=self.basepath)
        self.observer = Observer()
        self.observer.schedule(event_handler, self.basepath, recursive=True)
        self.observer.start()
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            snapshot = DirectorySnapshot(self.basepath, recursive=True)
            pickle.dump(snapshot, open("data/local_snapshot.p", "wb"))
            self.observer.stop()
        self.observer.join()

