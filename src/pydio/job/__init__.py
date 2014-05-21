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
from functools import wraps
import logging
import threading
import time


class ThreadManger(object):
    def __init__(self):
        self._threads = set()
        self.continue_run = True

    def manage(self, thread):
        logging.debug("Storing reference to thread: %s" % thread)
        self._threads.add(thread)

    def stop_all(self):
        logging.debug("Stopping managed threads: %s" % self._threads)
        self.continue_run = False
        for thread in self._threads:
            logging.debug("Stopping thread: %s" % thread)
            try:
                thread.stop()
            except Exception as ex:
                logging.warning("Could not stop thread: %s", thread,  exc_info=ex)

    def log_threads(self):
        for thread in threading.enumerate():
            logging.debug("thread: %s" % thread)

    def wait_more(self):
        while threading.active_count() > 1:
            logging.debug("There are %d threads still running" % threading.active_count())
            self.log_threads()
            time.sleep(5)

    def wait(self):
        try:
            time.sleep(5)
            self.log_threads()
            logging.debug("Waiting for exit")
            time.sleep(5000)
        except KeyboardInterrupt, ex:
            logging.error(ex, exc_info=True)
            manager.stop_all()
            self.wait_more()



manager = ThreadManger()


def stop_on_keyboard_interrupt(thread_run_function):
    """
    Wrapper for thread run functions that will catch KeyboardInterrupt and stop other threads
    """
    @wraps(thread_run_function)
    def wrapper(*args, **kwds):
        try:
            manager.manage(threading.current_thread())
            thread_run_function(*args, **kwds)
        except KeyboardInterrupt:
            logging.debug(u"KeyboardInterrupt, shutting down all threads")
            manager.stop_all()
        except SystemExit:
            logging.debug(u"SystemExit, shutting down all threads")
            manager.stop_all()
    return wrapper


def run_loop(thread_run_function):
    """
    Wrapper for thread target functions that will run in a loop
    and catch KeyboardInterrupt to stop and notify other threads
    """
    @wraps(thread_run_function)
    def wrapper(*args, **kwds):
        try:
            thread = threading.current_thread()
            manager.manage(thread)
            while manager.continue_run:
                logging.debug("Run loop start")
                thread_run_function(*args, **kwds)
        except KeyboardInterrupt:
            logging.debug(u"KeyboardInterrupt, shutting down all threads")
            manager.stop_all()
        except SystemExit:
            logging.debug(u"SystemExit, shutting down all threads")
            manager.stop_all()
    return wrapper


class PydioThread(threading.Thread):
    @stop_on_keyboard_interrupt
    def run(self):
        super(PydioThread, self).run()
