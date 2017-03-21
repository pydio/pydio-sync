#
# Copyright 2007-2014 Charles du Jeu - Abstrium SAS <team (at) pyd.io>
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
from memory_profiler import profile
import logging
import sys

class LogFile(object):
    """File-like object to log text using the `logging` module."""

    def __init__(self, name=None):
        self.logger = logging.getLogger(name)

    def write(self, msg, level=logging.INFO):
        if "MiB" in msg and float(msg.split("MiB")[1].strip())>0:
            self.logger.log(level, msg)
        elif msg.__contains__("Filename:") or msg.__contains__("Line Contents"):
            self.logger.log(level, msg)

    def flush(self):
        for handler in self.logger.handlers:
            handler.flush()

def pydio_profile(func=None, stream=None, precision=6):
    """
    Pydio wrapper for profile function from memory_profiler module

    :type
        precision: integer
        stream: i/o stream
        func: function
    """
    if sys.argv.__contains__('-mp=True') or sys.argv.__contains__('--memory_profile=True'):
        return profile(func, stream, precision)
    elif sys.argv.__contains__('-mp') or sys.argv.__contains__('--memory_profile'):
        index = sys.argv.index('-mp') if sys.argv.__contains__('-mp') else sys.argv.index('--memory_profile')
        return profile(func, stream, precision) if (str(sys.argv[index+1]).lower() == 'true') else func
    else:
        return func

