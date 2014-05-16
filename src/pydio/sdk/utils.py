import logging
import requests

from io import BytesIO


class BytesIOWithCallback(BytesIO):
    def __init__(self, data_buffer=None, callback=None):
        self.callback = callback
        self.progress = 0
        self.length = len(data_buffer)
        BytesIO.__init__(self, data_buffer)

    def __len__(self):
        return self.length

    def read(self, n=-1):
        if self.callback:
            try:
                self.callback(self.length, self.progress)
            except:
                logging.warning('Buffered reader callback error')
                return None

        chunk = BytesIO.read(self, n)
        self.progress += int(len(chunk))

        return chunk


def upload_file_showing_progress(url, fields, auth):
    (data, content_type) = requests.packages.urllib3.filepost.encode_multipart_formdata(fields)
    body = BytesIOWithCallback(data, log_progress)

    return requests.post(
        url,
        data=body,
        headers={'Content-Type': content_type},
        auth=auth
    )


def log_progress(size=0, progress=0):
    logging.info('File upload progress is {0:.2f}%'.format(float(progress)/size*100))
