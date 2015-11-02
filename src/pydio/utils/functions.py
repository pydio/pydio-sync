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
import os,sys
import urllib2


def hashfile(afile, hasher, blocksize=65536):
    buf = afile.read(blocksize)
    while len(buf) > 0:
        hasher.update(buf)
        buf = afile.read(blocksize)
    return hasher.hexdigest()


def set_file_hidden(path):
    if os.name in ("nt", "ce"):
        import ctypes
        ctypes.windll.kernel32.SetFileAttributesW(path, 2)


def get_user_home(app_name):
    if sys.platform == 'win32':
        from arch.win.expanduser import expand_user as win_expand
        return os.path.join(win_expand(), app_name)
    else:
        return os.path.join(os.path.expanduser('~'), app_name)


def guess_filesystemencoding():
    fse = sys.getfilesystemencoding()
    if not fse and sys.platform.startswith('linux'):
        fse = 'utf-8'
    return fse


class ConnectionHelper:

    def __init__(self):
        self.internet_ok = True

    def is_connected_to_internet(self, proxies):
        try:
            proxy = urllib2.ProxyHandler(proxies)
            opener = urllib2.build_opener(proxy)
            urllib2.install_opener(opener)
            urllib2.urlopen('http://www.google.com', timeout=1)
            self.internet_ok = True
            return True
        except Exception as e:
            pass
        self.internet_ok = False
        return False

connection_helper = ConnectionHelper()

class Singleton:

    def __init__(self, decorated):
        self._decorated = decorated

    def Instance(self, **kwargs):
        try:
            return self._instance
        except AttributeError:
            self._instance = self._decorated(**kwargs)
            return self._instance

    def __call__(self):
        raise TypeError('Singletons must be accessed through `Instance()`.')

    def __instancecheck__(self, inst):
        return isinstance(inst, self._decorated)