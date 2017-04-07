#
# Copyright 2007-2015 Charles du Jeu - Abstrium SAS <team (at) pyd.io>
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
import os
from win32com.client import Dispatch


def create_shortcut(path, target='', wDir='', icon=''):
    if os.path.exists(path):
        os.unlink(path)
    ext = path[-3:]
    if ext == 'url':
        shortcut = file(path, 'w')
        shortcut.write('[InternetShortcut]\n')
        shortcut.write('URL=%s' % target)
        shortcut.close()
    else:
        shell = Dispatch('WScript.Shell')
        shortcut = shell.CreateShortCut(path)
        shortcut.Targetpath = target
        shortcut.WorkingDirectory = wDir
        if icon == '':
            pass
        else:
            shortcut.IconLocation = icon
        shortcut.save()


def win_add_to_favorites(path, label):
    # Use %USERPROFILE%/Links folder or %USERPROFILE%/Favorites for earlier win versions
    base = os.environ.get("USERPROFILE")
    if not base:
        return
    user_favs = os.path.join(base, 'Links')
    alt_favs = os.path.join(base, 'Favorites')
    if os.path.exists(user_favs):
        create_shortcut(os.path.join(user_favs, label + '.lnk'), path, '', '')
    elif os.path.exists(alt_favs):
        create_shortcut(os.path.join(alt_favs, label + '.lnk'), path, '', '')
