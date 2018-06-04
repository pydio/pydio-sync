#
#  Copyright 2007-2014 Charles du Jeu - Abstrium SAS <team (at) pyd.io>
#  This file is part of Pydio.
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
from functools import wraps
import logging
import threading
import sys
import time
try:
    from pydio.sdkremote.remote import Waiter
    from pydio.job.local_watcher import LocalWatcher
except ImportError:
    from sdkremote.remote import Waiter
    from job.local_watcher import LocalWatcher


class ThreadManager(object):
    def __init__(self):
        self.continue_run = True
        self.api_server = None

    def manage(self, thread):
        logging.debug("Storing reference to thread: %s" % thread)

    def stop_all(self):
        logging.debug("Stopping managed threads")
        self.continue_run = False
        for thread in self.managed_threads():
            if not hasattr(thread, "stop"):
                logging.warning("Could not stop %s" % thread)
                continue
            logging.debug("Stopping thread: %s" % thread)
            thread.stop()

        # this needs troubleshooting, if a cleaner exit is needed for flask server
        # logging.debug("self.api_server: %s" % self.api_server)
        # self.api_server.shutdown_server()

    def managed_threads(self):
        for thread in threading.enumerate():
            if thread == threading.current_thread() or getattr(thread, "daemon", False):
                continue
            yield thread

    def are_threads_running(self):
        return len(list(self.managed_threads())) > 0

    def shutdown_wait(self):
        while self.are_threads_running():
            potential_important_thread = False
            for t in self.managed_threads():
                if type(t) != Waiter and type(t) != LocalWatcher:
                    potential_important_thread = True
            if potential_important_thread:
                logging.debug("There are %d threads still running" % threading.active_count())
                logging.debug("Threads: \n\t%s" % "\n\t".join([str(t) for t in threading.enumerate()]))
                time.sleep(2)
            else:
                # force exit when only websocket and localwatcher threads are running
                sys.exit(0)

    def wait(self):
        try:
            time.sleep(1)
            logging.debug("Threads: \n\t%s" % "\n\t".join([str(t) for t in threading.enumerate()]))
            if not self.are_threads_running:
                logging.debug("No threads to wait for")
                return
            logging.debug("Waiting for exit")
            while self.continue_run:
                time.sleep(5)
            logging.debug("ThreadManager is no longer waiting")
        except KeyboardInterrupt, ex:
            logging.debug("KeyboardInterrupt, shutting down.")
            manager.stop_all()
            self.shutdown_wait()


def run_loop(thread_run_function):
    """
    Wrapper for thread target functions that will run in a loop
    and catch KeyboardInterrupt to stop and notify other threads
    """
    @wraps(thread_run_function)
    def wrapper(*args, **kwds):
        while manager.continue_run:
            logging.debug("Run loop start")
            thread_run_function(*args, **kwds)
    return wrapper

manager = ThreadManager()
