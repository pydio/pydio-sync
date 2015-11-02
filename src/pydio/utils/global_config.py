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
import uuid, json,logging
import keyring


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
            with open(self.configs_path + '/device_id', 'rb') as f:
                self.device_id = pickle.load(f)
            return self.device_id

        self.device_id = str(uuid.uuid1())
        with open(self.configs_path + '/device_id', 'wb') as f:
            pickle.dump(self.device_id, f)
        return self.device_id

    def get_version_data(self):
        from pydio.version import version, build, version_date
        return {'version': version, 'build':build, 'date':version_date}

    def get_defined_proxies(self):
        if not self.proxies_loaded:
            # Try to load data from self.configs_path/proxies.json
            proxies_file = self.configs_path + '/proxies.json'
            data = ""
            if os.path.exists(proxies_file):
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
        return self.proxies

    def check_proxy(self, data):
            """
            Check if the proxy is up by trying to open a well known url via proxy
            """
            #logging.info(data)
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

                import urllib2
                #urllib.urlopen("http://www.google.com", proxies=proxies)
                proxy = urllib2.ProxyHandler(proxies)
                opener = urllib2.build_opener(proxy)
                urllib2.install_opener(opener)
                resp = urllib2.urlopen('http://www.google.com')
                logging.info("[Proxy info] Server is reachable via proxy from client")
                return resp.code == 200
            except IOError:
                logging.error("[Proxy info] Connection error! (Check proxy)")
            return False

    def set_user_proxy(self, data):
        """
        Set the proxy by writing the contents to a file (usually proxies.json)

        :param data: list with 4 entries [username,password,proxyIP,proxyPort]
        :return: response
        """
        file_name = os.path.join(self.configs_path, 'proxies.json')
        try:
            with open(file_name, 'w') as f:
                json.dump(data, f)
        except Exception as ex:
            logging.exception(ex)
        return "write to Proxies.json file is successful"
