import logging
import requests
import time
import os
import stat
import math

from io import BytesIO, FileIO
from pydispatch import dispatcher
from pydio import TRANSFER_RATE_SIGNAL
from six import b

class BytesIOWithFile(BytesIO):

    def __init__(self, data_buffer, closing_boundary, filename, callback=None, chunk_size=0, file_part=0):

        self.callback = callback
        self.cursor = 0
        self.start = time.clock()
        self.closing_boundary = closing_boundary
        self.data_buffer_length = len(data_buffer)
        self.file_length = os.stat(filename).st_size
        self.full_length = self.length = self.data_buffer_length + self.file_length + len(closing_boundary)

        self.chunk_size=chunk_size
        self.file_part=file_part
        self.seek = 0

        self.fd = open(filename, 'rb')
        if chunk_size and self.file_length > chunk_size:
            seek = file_part * chunk_size
            self.seek = seek
            self.fd.seek(seek)
            # recompute chunk_size
            if self.file_length - seek < chunk_size:
                self.chunk_size = self.file_length - seek
            self.length = self.chunk_size + self.data_buffer_length + len(closing_boundary)

        BytesIO.__init__(self, data_buffer)

    def __len__(self):
        return self.length

    def read(self, n=-1):

        transfer_rate = self.cursor//(time.clock() - self.start)
        if self.callback:
            try:
                self.callback(self.full_length, self.cursor * (self.file_part+1), transfer_rate)
            except:
                logging.warning('Buffered reader callback error')
                return None
        dispatcher.send(signal=TRANSFER_RATE_SIGNAL, send=self, transfer_rate=transfer_rate)

        if self.cursor >= self.length:
            # EOF
            return
        if self.cursor >= (self.length - len(self.closing_boundary)):
            # CLOSING BOUNDARY
            chunk = self.closing_boundary
        elif self.cursor >= self.data_buffer_length:
            # FILE CONTENT
            if (self.length - len(self.closing_boundary)) - self.cursor <= n:
                n = (self.length - len(self.closing_boundary)) - self.cursor
            chunk = self.fd.read(n)
        else:
            # ENCODED PARAMETERS
            chunk = BytesIO.read(self, n)

        self.cursor += int(len(chunk))
        return chunk


def encode_multiparts(fields):

    (data, content_type) = requests.packages.urllib3.filepost.encode_multipart_formdata(fields)
    logging.debug(data)

    header_body = BytesIO()

    # Remove closing boundary
    lines = data.split("\r\n")
    boundary = lines[0]
    lines = lines[0:len(lines)-2]
    header_body.write(b("\r\n".join(lines) + "\r\n"))

    #Add file data part except data
    header_body.write(b('%s\r\n' % boundary))
    header_body.write(b('Content-Disposition: form-data; name="userfile_0"; filename="fake-name"\r\n'))
    header_body.write(b('Content-Type: application/octet-stream\r\n\r\n'))

    closing_boundary = b('\r\n%s--\r\n' % (boundary))

    return (header_body.getvalue(), closing_boundary, content_type)


def upload_file_with_progress(url, fields, files, stream, with_progress, max_size=0):

    if with_progress:
        def cb(size=0, progress=0, rate=0):
            with_progress['progress'] = float(progress)/size*100
            with_progress['remaining_bytes'] = size - progress
            with_progress['transfer_rate'] = rate
    else:
        cb = log_progress

    filesize = os.stat(files['userfile_0']).st_size

    (header_body, close_body, content_type) = encode_multiparts(fields)
    body = BytesIOWithFile(header_body, close_body, files['userfile_0'], callback=cb, chunk_size=max_size, file_part=0)
    resp = requests.post(
        url,
        data=body,
        headers={'Content-Type':content_type},
        stream=True
    )

    if resp.status_code == 401:
        return resp

    if max_size and filesize > max_size:
        fields['appendto_urlencoded_part'] = fields['urlencoded_filename']
        del fields['urlencoded_filename']
        (header_body, close_body, content_type) = encode_multiparts(fields)
        for i in range(1, int(math.ceil(filesize / max_size)) + 1):
            body = BytesIOWithFile(header_body, close_body, files['userfile_0'], callback=cb, chunk_size=max_size, file_part=i)
            resp = requests.post(
                url,
                data=body,
                headers={'Content-Type':content_type},
                stream=True
            )

    return resp
