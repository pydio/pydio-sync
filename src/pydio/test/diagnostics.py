import logging
import multiprocessing
import sys
#import zmq

from pydio.sdk.remote import PydioSdk


class PydioDiagnostics():

    def __init__(self, url, basepath, ws_id, user_id):
        self.url = url
        self.basepath = basepath
        self.ws_id = ws_id
        self.user_id = user_id
        self.status = 0
        self.status_message = None

    def run(self):
        self.run_ping_server_test()
        return self.status

    def run_ping_server_test(self):
        logging.info('---- Server ping test ---')
        assert self.url
        assert self.basepath
        assert self.user_id
        if not all([self.url, self.basepath, self.user_id]):
            logging.info('Can not run ping server test, please provide: ')
            logging.info('--server --directory --workspace --user --password')
            self.status = -1
            self.status_message = "Can not run ping server test, please provide configuration arguments"
            return

        pydio_sdk = PydioSdk(self.url, self.basepath, self.ws_id or '', self.user_id)
        success = pydio_sdk.stat(unicode('/', 'utf-8'))
        logging.info('Server ping test: %s' % ('success' if success else 'failure'))
        if not success:
            self.status = -1
            self.status_message = "Server ping test: failure"
            return

