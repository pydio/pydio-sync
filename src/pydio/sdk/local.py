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
import subprocess
import os
import hashlib
import stat
from exceptions import SystemSdkException
from pydio.utils.functions import hashfile
from pydio.utils.global_config import ConfigManager
import shutil
from pydio.utils import i18n
_ = i18n.language.ugettext

class SystemSdk(object):

    def __init__(self, basepath):
        """
        Encapsulate some filesystem functions. We should try to make SystemSdk and PydioSdk converge
        with a same interface, wich would allow syncing any "nodes", not necessarily one remote and one local.
        :param basepath: root folder path
        :return:
        """
        self.signature_extension = '.sync_signature'
        self.delta_extension = '.sync_delta'
        self.path_extension = '.sync_patched'
        self.basepath = basepath
        self.rdiff_path = ConfigManager.Instance().get_rdiff_path()

    def check_basepath(self):
        """
        Check if basepath exists or not
        :return: bool
        """
        return os.path.exists(self.basepath)

    def bulk_stat(self, pathes, with_hash=False):
        return None


    def stat(self, path, full_path=False, with_hash=False):
        """
        Format filesystem stat in the same way as it's returned by server for remote stats.
        :param path:local path (starting from basepath)
        :param full_path:optionaly pass full path
        :param with_hash:add file content hash in the result
        :return:dict() an fstat lile result:
        {
            'size':1231
            'mtime':1214365
            'mode':0255
            'inode':3255
            'hash':'1F3R4234RZEdgFGD'
        }
        """
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
        """
        Delete a folder recursively on filesystem
        :param path:Path of the folder to remove, starting from basepath
        :return:bool True
        """
        if not os.path.exists(self.basepath + path):
            return True
        try:
            shutil.rmtree(self.basepath + path)
            #os.rmdir(self.basepath + path)
        except OSError as e:
            raise SystemSdkException('delete', path, _('Cannot remove local folder'))

    def rsync_signature(self, file_path, signature_path):
        if not self.rdiff_path:
            return
        subprocess.check_call([self.rdiff_path, 'signature', os.path.join(self.basepath, file_path.strip("\\")), os.path.join(self.basepath, signature_path.strip("\\"))])

    def rsync_delta(self, file_path, signature_path, delta_path):
        if not self.rdiff_path:
            return
        subprocess.check_call([self.rdiff_path, 'delta', signature_path, file_path, delta_path])

    def rsync_patch(self, file_path, delta_path, output_path=''):
        if not self.rdiff_path:
            return
        if not output_path:
            output_path = file_path + ".patched"
        subprocess.check_call([self.rdiff_path, 'patch', file_path, delta_path, output_path])
        if os.path.exists(output_path) and os.path.getsize(output_path):
            os.unlink(file_path)
            os.rename(output_path, file_path)