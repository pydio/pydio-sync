import os
import sys
import logging
import time

from requests.exceptions import ConnectionError
import zmq

if __name__ == "__main__":
    context = zmq.Context()
    socket = context.socket(zmq.REQ)
    socket.connect("tcp://localhost:%s" % 5557)

    for f in sys.argv[1:]:
        socket.send("CMD Share file " + f)