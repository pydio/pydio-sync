import logging
import requests
import time

from io import BytesIO
from pydispatch import dispatcher
from pydio import TRANSFER_RATE_SIGNAL

class BytesIOWithCallback(BytesIO):
    def __init__(self, data_buffer=None, callback=None):
        self.callback = callback
        self.progress = 0
        self.length = len(data_buffer)
        BytesIO.__init__(self, data_buffer)
        self.start = time.clock()

    def __len__(self):
        return self.length

    def read(self, n=-1):

        transfer_rate = self.progress//(time.clock() - self.start)
        if self.callback:
            try:
                self.callback(self.length, self.progress, transfer_rate)
            except:
                logging.warning('Buffered reader callback error')
                return None
        dispatcher.send(signal=TRANSFER_RATE_SIGNAL, send=self, transfer_rate=transfer_rate)

        chunk = BytesIO.read(self, n)
        self.progress += int(len(chunk))

        return chunk


def upload_file_showing_progress(url, fields, stream, with_progress=None):
    (data, content_type) = requests.packages.urllib3.filepost.encode_multipart_formdata(fields)
    if with_progress:
        def cb(size=0, progress=0, rate=0):
            with_progress['progress'] = float(progress)/size*100
            with_progress['remaining_bytes'] = size - progress
            with_progress['transfer_rate'] = rate
    else:
        cb = log_progress

    body = BytesIOWithCallback(data, cb)

    return requests.post(
        url,
        data=body,
        headers={'Content-Type': content_type},
        stream=stream
    )


def log_progress(size=0, progress=0, rate=0):
    logging.info('File upload progress is {0:.2f}%, ETA is '.format(float(progress)/size*100, rate))
