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
    device_id = ''
    data_path = ''
    rdiff_path = ''
    proxies = None
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

    def get_device_id(self):
        if self.device_id:
            return self.device_id

        if osp.exists(self.configs_path + '/device_id'):
            with open(self.configs_path + '/device_id', 'rb') as f:
                self.device_id = pickle.load(f)
            return self.device_id

        self.device_id = str(uuid.uuid1())
        with open(self.configs_path + '/device_id', 'wb') as f:
            pickle.dump(self.device_id, f)
        return self.device_id

    def get_version_data(self):
        try:
            from pydio.version import version, build, version_date
        except ImportError:
            from version import version, build, version_date
        return {'version': version, 'build':build, 'date':version_date}

    def get_defined_proxies(self):
        if not self.proxies_loaded:
            # Try to load data from self.configs_path/proxies.json
            proxies_file = self.configs_path + '/proxies.json'
            data = ""
            if osp.exists(proxies_file):
                try:
                    with open(proxies_file, 'r') as handle:
                        data = json.load(handle)
                    if isinstance(data, dict):
                        proxies = {}
                        for protocol in data.keys():
                            if data[protocol]["password"] =="__pydio_proxy_pwd__":
                                proxy = protocol + '://' + data[protocol]["username"] + ':' + keyring.get_password(data[protocol]["hostname"], data[protocol]["username"]) + '@' + data[protocol]["hostname"] + ':' + data[protocol]["port"]
                            elif data[protocol]["password"] == "" and data[protocol]["username"] == "":
                                proxy = protocol + '://' + data[protocol]["hostname"] + ':' + data[protocol]["port"]
                            else:
                                proxy = protocol + '://' + data[protocol]["username"] + ':' + data[protocol]["password"] + '@' + data[protocol]["hostname"] + ':' + data[protocol]["port"]
                            proxies[protocol] = proxy
                        self.proxies = proxies
                    else:
                        logging.error('The proxy data is not the form of dict obj')
                except Exception as e:
                    logging.exception(e)
                    logging.error('Error while trying to load proxies.json file')

            if data != "":
                for k in data.keys():
                    if "active" in data[k]:
                        if data[k]["active"] == True or data[k]["active"] == "true":
                            self.check_proxy(data)
                        else: # if proxies aren't marked active forget about them
                            data = "" # !! dangerous mutation
                            self.proxies = {}
                            break
            self.proxies_loaded = True
            #logging.info("[Proxy info] " + str(self.proxies))
        if not self.proxies:
            self.proxies = {}
        return self.proxies

    def check_proxy(self, data):
            """
            Check if the proxy is up by trying to open a well known url via proxy
            """
            try:
                proxies = {}
                for protocol in data.keys():
                    if data[protocol]["password"] =="__pydio_proxy_pwd__":
                        proxy = protocol + '://' + data[protocol]["username"] + ':' + keyring.get_password(data[protocol]["hostname"], data[protocol]["username"]) + '@' + data[protocol]["hostname"] + ':' + data[protocol]["port"]
                    elif data[protocol]["password"] == "" and data[protocol]["username"] == "":
                        proxy = protocol + '://' + data[protocol]["hostname"] + ':' + data[protocol]["port"]
                    else:
                        proxy = protocol + '://' + data[protocol]["username"] + ':' + data[protocol]["password"] + '@' + data[protocol]["hostname"] + ':' + data[protocol]["port"]
                    proxies[protocol] = proxy

                import requests
                resp = requests.get("http://www.google.com", proxies=proxies)
                logging.info("[Proxy info] Server is reachable via proxy from client")
                return resp.status_code == 200
            except IOError:
                logging.error("[Proxy info] Connection error! (Check proxy)")
            return False

    def set_user_proxy(self, data):
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
