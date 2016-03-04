#
# Copyright 2007-2014 Charles du Jeu - Abstrium SAS <team (at) pyd.io>
# This file is part of Pydio.
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

import logging
import multiprocessing
import sys
#import zmq
try:
    from pydio.utils.global_config import ConfigManager
    from pydio.utils.pydio_profiler import pydio_profile
    from pydio.sdk.remote import PydioSdk
except ImportError:
    from utils.global_config import ConfigManager
    from utils.pydio_profiler import pydio_profile
    from sdk.remote import PydioSdk

class PydioDiagnostics():

    def __init__(self, url, basepath, ws_id, user_id, password=None):
        self.url = url
        self.basepath = basepath
        self.ws_id = ws_id
        self.user_id = user_id
        self.password = password
        self.status = 0
        self.status_message = None

    def run(self):
        self.run_ping_server_test()
        return self.status

    @pydio_profile
    def run_ping_server_test(self):
        logging.info('---- Server ping test ---')
        logging.debug("self.url: %s" % self.url)
        logging.debug("self.basepath: %s" % self.basepath)
        logging.debug("self.user_id: %s" % self.user_id)
        assert self.url
        assert self.basepath
        assert self.user_id
        if not all([self.url, self.basepath, self.user_id]):
            logging.info('Can not run ping server test, please provide: ')
            logging.info('--server --directory --workspace --user --password')
            self.status = 146
            self.status_message = "Can not run ping server test, please provide configuration arguments"
            return

        if self.password:
            pydio_sdk = PydioSdk(self.url, self.basepath, self.ws_id or '',
                                 user_id='', auth=(self.user_id, self.password),
                                 device_id=ConfigManager.Instance().get_device_id())
        else:
            pydio_sdk = PydioSdk(self.url, self.basepath, self.ws_id or '',
                                 user_id=self.user_id, device_id=ConfigManager.Instance().get_device_id())
        success = pydio_sdk.stat(unicode('/', 'utf-8'))
        logging.info('Server ping on %s with user/pass %s/%s: %s' % (self.url, self.user_id, self.password, 'success' if success else 'failure'))
        if not success:
            self.status = 147
            self.status_message = "Server ping test: failure"
            return

        import os
        import requests
        if 'REQUESTS_CA_BUNDLE' in os.environ and not os in ["ce", "nt"]:
            logging.info("Certificate path is " + os.environ['REQUESTS_CA_BUNDLE'])
            data = requests.get('https://google.com', verify=os.environ['REQUESTS_CA_BUNDLE'],
                                proxies=ConfigManager.Instance().get_defined_proxies())
            logging.info(data)
