import multiprocessing
import zmq

from pydio.sdk.remote import PydioSdk


class SmokeTests():

    zmq_address = 'tcp://127.0.0.1:5678'

    def __init__(self, url, basepath, ws_id, user_id):
        self.url = url
        self.basepath = basepath
        self.ws_id = ws_id
        self.user_id = user_id

    def run(self):
        # self.run_zmq_smoke_test()
        self.run_ping_server_test()

    @classmethod
    def run_zmq_smoke_test(cls):
        print 'Start ZMQ test'
        receive_process = multiprocessing.Process(
            target=cls._receive_message_from_zmq_and_send_reply)
        receive_process.start()
        cls._send_message_to_zmq_and_wait_for_reply()
        receive_process.join()

    @classmethod
    def _send_message_to_zmq_and_wait_for_reply(cls):
        context = zmq.Context()
        sock = context.socket(zmq.REQ)
        sock.bind(cls.zmq_address)

        message = '--- Test message send to zmq ---'
        print('Sending request: %s' % message)
        sock.send_unicode(message)
        response = sock.recv_unicode()
        print('Receiving response: %s' % response)

    @classmethod
    def _receive_message_from_zmq_and_send_reply(cls):
        context = zmq.Context()
        sock = context.socket(zmq.REP)
        sock.connect(cls.zmq_address)

        request = sock.recv_unicode()
        print('Receiving request: %s' % request)
        message = 'Test response sent to zmq'
        print('Sending response: %s' % message)
        sock.send_unicode(message)

    def run_ping_server_test(self):
        print '---- Server ping test ---'
        if not all([self.url, self.basepath, self.user_id]):
            print 'Can not run ping server test, please provide: '
            print '--server --directory --workspace --user --password'
            return

        pydio_sdk = PydioSdk(self.url, self.basepath, self.ws_id or '', self.user_id)
        test_result = 'success' if pydio_sdk.stat('/') else 'failure'
        print ('Server ping test: %s' % test_result)