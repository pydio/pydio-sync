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
import os
import hashlib
import stat
from exceptions import SystemSdkException
from pydio.utils.functions import hashfile

class SystemSdk(object):

    def __init__(self, basepath):
        self.basepath = basepath

    def check_basepath(self):
        return os.path.exists(self.basepath)

    def stat(self, path, full_path=False, with_hash=False):
        if not path:
            return False
        if not full_path:
            path = self.basepath + path
        if not os.path.exists(path):
            return False
        else:
            stat_result = os.stat(path)
            s = dict()
            s['size'] = stat_result.st_size
            s['mtime'] = stat_result.st_mtime
            s['mode'] = stat_result.st_mode
            s['inode'] = stat_result.st_ino
            if with_hash:
                if stat.S_ISREG(stat_result.st_mode):
                    s['hash'] = hashfile(open(path, 'rb'), hashlib.md5())
                elif stat.S_ISDIR(stat_result.st_mode):
                    s['hash'] = 'directory'
            return s

    def rmdir(self, path):
        if not os.path.exists(self.basepath + path):
            return True
        try:
            os.rmdir(self.basepath + path)
        except OSError as e:
            raise SystemSdkException('delete', path, 'cannot remove folder')
