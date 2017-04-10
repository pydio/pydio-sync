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
import os.path as osp
import time
import uuid, json,logging
import keyring

DEFAULT_CONFIG = dict(update_info={"enable_update_check": "True",
                                   "update_check_frequency_days": 1,
                                   "last_update_date": 0},
                      max_wait_time_for_local_db_access=30,
                      language="")


@Singleton
class ConfigManager:
    _device_id = ''
    data_path = ''
    rdiff_path = ''
    proxies = {}
    proxies_loaded = False

    def __init__(self, configs_path, data_path):
        self.configs_path = configs_path
        self.data_path = data_path
        self.general_config = None
        self.last_load = 0

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

    @property
    def device_id(self):
        if self._device_id:
            return self._device_id

        dvc_id = os.path.join(self.configs_path, 'device_id')
        if osp.exists(dvc_id):
            with open(dvc_id, 'rb') as f:
                self._device_id = pickle.load(f)
            return self._device_id

        self._device_id = str(uuid.uuid1())
        with open(dvc_id, 'wb') as f:
            pickle.dump(self._device_id, f)

        return self._device_id

    @property
    def version_info(self):
        try:
            from pydio.version import version, build, version_date
        except ImportError:
            from version import version, build, version_date
        return {'version': version, 'build': build, 'date': version_date}

    def _format_proxy(self, proxy_data, proto, short=False):
        hostnm = proxy_data[proto]["hostname"]
        pnumbr = proxy_data[proto]["port"]
        usrname = proxy_data[proto].get("username")
        passwd = keyring.get_password(hostnm, usrname)
        if short:
            return "{scheme}://{host}:{port}".format(
                scheme=proto,
                host=hostnm,
                port=pnumbr,
            )
        return "{scheme}://{usr}:{pwd}@{host}:{port}".format(
            scheme=proto,
            usr=usrname,
            pwd=passwd,
            host=hostnm,
            port=pnumbr
        )

    def _load_proxies(self):
        """Try to load data from self.configs_path/proxies.json"""
        proxies_file = osp.join(self.configs_path, "proxies.json")
        data = None
        if osp.exists(proxies_file):
            with open(proxies_file) as f:
                data = json.load(f)

            if not isinstance(data, dict):
                emsg = "Proxy data must be dict, got {0}"
                raise TypeError(emsg.format(type(data)))

            proxies = {}
            for proto in data:
                if data[proto]["password"] == "__pydio_proxy_pwd__":
                    proxy = self._format_proxy(data, proto)
                elif data[proto]["password"] and data[proto]["username"]:
                    proxy = self._format_proxy(data, proto, short=True)
                else:
                    proxy = self._format_proxy(data, proto)

                proxies[proto] = proxy

            self.proxies = proxies

        if data:
            for k in data:
                if data[k].get("active") or data[k]["active"] == "true":
                    self.check_proxy(data)
                else: # if proxies aren't marked active forget about them
                    data = "" # !! dangerous mutation
                    self.proxies = {}
                    break

    @property
    def defined_proxies(self):
        if not self.proxies_loaded:
            self._load_proxies()
            self.proxies_loaded = True

        return self.proxies

    def check_proxy(self, data):
        """Check if the proxy is up by trying to open a well known url."""
        try:
            proxies = {}
            for proto in data.keys():
                if data[proto]["password"] =="__pydio_proxy_pwd__":
                    proxy = self._format_proxy(data, proto)
                elif data[proto]["password"] == "" and data[proto]["username"] == "":
                    proxy = self._format_proxy(data, proto, short=True)
                else:
                    proxy = self._format_proxy(data, proto)
                proxies[proto] = proxy

            import requests
            resp = requests.get("http://www.google.com", proxies=proxies)
            logging.info("[ Proxy Info ] Server is reachable via proxy")
            return resp.status_code == 200
        except IOError:
            logging.error("[ Proxy Info ] Connection error! (Check proxy)")

        return False

    def save_proxy_config(self, data):
        """
        Set the proxy by writing the contents to a file (usually proxies.json)

        :param data: list with 4 entries [username,password,proxyIP,proxyPort]
        :return: response
        """
        file_name = osp.join(self.configs_path, 'proxies.json')
        try:
            with open(file_name, 'w') as f:
                json.dump(data, f, indent=4, separators=(',', ': '))
        except Exception as ex:
            logging.exception(ex)
        return "write to Proxies.json file is successful"

@Singleton
class GlobalConfigManager:

    def __init__(self, configs_path=None):
        if configs_path is not None:
            self.configs_path = configs_path
        self.default_settings = DEFAULT_CONFIG

    def set_general_config(self, data):
        """
        Put the global configurations into general_config.json if it doesn't exist
        :param data: dict object with configuration data
        """
        global_config_file = osp.join(self.configs_path, 'general_config.json')
        self.last_load = 0
        # Set the global config only if no prior settings exists
        if not osp.exists(global_config_file) or os.stat(global_config_file).st_size == 0:
            if not osp.exists(self.configs_path):
                os.makedirs(self.configs_path)
            with open(global_config_file, 'w') as conf_file:
                json.dump(data, conf_file, indent=4, separators=(',', ': '))

    def update_general_config(self, data):
        """
        Update the global configurations into general_config.json
        :param data: dict object with configuration data
        """
        self.last_load = 0
        with open(osp.join(self.configs_path, 'general_config.json'), 'w') as conf_file:
            json.dump(data, conf_file, indent=4, separators=(',', ': '))

    def get_general_config(self):
        """
        Fetch the config details from general_config.json file
        :return: dict object with configuration data
        """
        with open(osp.join(self.configs_path, 'general_config.json')) as conf_file:  # memoize general config, don't reload the file more than every 3 seconds
            if time.time() - self.last_load > 5:
                self.last_load = time.time()
                self.general_config = json.load(conf_file)
            return self.general_config
