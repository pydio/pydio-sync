import logging
import multiprocessing
import sys
#import zmq

from pydio.sdk.remote import PydioSdk


class PydioDiagnostics():
    # zmq_address = 'tcp://127.0.0.1:5678'
    #
    def __init__(self, url, basepath, ws_id, user_id):
        self.url = url
        self.basepath = basepath
        self.ws_id = ws_id
        self.user_id = user_id
        self.status = 0
        self.status_message = None

    def run(self):
        # self.run_zmq_smoke_test()
        self.run_ping_server_test()
        return self.status

    # @classmethod
    # def run_zmq_smoke_test(cls):
    #     logging.info('Start ZMQ test')
    #     receive_process = multiprocessing.Process(
    #         target=cls._receive_message_from_zmq_and_send_reply)
    #     receive_process.start()
    #     cls._send_message_to_zmq_and_wait_for_reply()
    #     receive_process.join()
    #
    # @classmethod
    # def _send_message_to_zmq_and_wait_for_reply(cls):
    #     context = zmq.Context()
    #     sock = context.socket(zmq.REQ)
    #     sock.bind(cls.zmq_address)
    #
    #     message = '--- Test message send to zmq ---'
    #     logging.info('Sending request: %s' % message)
    #     sock.send_unicode(message)
    #     response = sock.recv_unicode()
    #     logging.debug('Receiving response: %s' % response)
    #
    # @classmethod
    # def _receive_message_from_zmq_and_send_reply(cls):
    #     context = zmq.Context()
    #     sock = context.socket(zmq.REP)
    #     sock.connect(cls.zmq_address)
    #
    #     request = sock.recv_unicode()
    #     logging.info('Receiving request: %s' % request)
    #     message = 'Test response sent to zmq'
    #     logging.debug('Sending response: %s' % message)
    #     sock.send_unicode(message)

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
        success = pydio_sdk.stat('/')
        logging.info('Server ping test: %s' % ('success' if success else 'failure'))
        if not success:
            self.status = -1
            self.status_message = "Server ping test: failure"
            return

