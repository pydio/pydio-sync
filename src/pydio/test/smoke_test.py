import multiprocessing
import zmq


class SmokeTests():

    zmq_address = 'tcp://127.0.0.1:5678'

    @classmethod
    def run(cls):
        cls.run_zmq_smoke_test()

    @classmethod
    def run_zmq_smoke_test(cls):
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

        message = 'Test message send to zmq'
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
