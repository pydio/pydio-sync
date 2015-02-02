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
from .functions import Singleton
import pickle
import os
import uuid

@Singleton
class ConfigManager:

    device_id = ''
    data_path = ''
    rdiff_path = ''

    def __init__(self, configs_path, data_path):
        self.configs_path = configs_path
        self.data_path = data_path

    def get_configs_path(self):
        return self.configs_path

    def get_data_path(self):
        return self.data_path

    def set_rdiff_path(self, rdiff_path):
        if rdiff_path is None:
            self.rdiff_path = False
        else:
            self.rdiff_path = rdiff_path

    def get_rdiff_path(self):
        return self.rdiff_path

    def get_device_id(self):
        if self.device_id:
            return self.device_id

        if os.path.exists(self.configs_path + '/device_id'):
            self.device_id = pickle.load(open(self.configs_path + '/device_id', 'rb'))
            return self.device_id

        self.device_id = str(uuid.uuid1())
        pickle.dump(self.device_id, open(self.configs_path + '/device_id', 'wb'))
        return self.device_id

    def get_version_data(self):
        from pydio.version import version, build, version_date
        return {'version': version, 'build':build, 'date':version_date}