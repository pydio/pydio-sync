#
#  Copyright 2007-2014 Charles du Jeu - Abstrium SAS <team (at) pyd.io>
#  This file is part of Pydio.
#
#  Pydio is free software: you can redistribute it and/or modify
#  it under the terms of the GNU Affero General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#
#  Pydio is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU Affero General Public License for more details.
#
#  You should have received a copy of the GNU Affero General Public License
#  along with Pydio.  If not, see <http://www.gnu.org/licenses/>.
#
#  The latest code can be found at <http://pyd.io/>.
#

import logging
import requests
import time
import os
import stat
import math

from io import BytesIO, FileIO
from pydispatch import dispatcher
from pydio import TRANSFER_RATE_SIGNAL, TRANSFER_CALLBACK_SIGNAL
from six import b
# -*- coding: utf-8 -*-

class BytesIOWithFile(BytesIO):

    def __init__(self, data_buffer, closing_boundary, filename, callback=None, chunk_size=0, file_part=0):
        """
        Class extending the standard BytesIO to read data directly from file instead of loading all file content
        in memory. It's initially started with all the necessary data to build the full body of the POST request,
        in an multipart-form-data encoded way.
        It can also feed progress data and transfer rates. When uploading file chunks through various queries, the
        progress takes also into account the fact that this may be the part XX of a larger file.

        :param data_buffer: All the beginning of the multipart data, until the opening of the file content field
        :param closing_boundary: Last data to add after the file content has been sent.
        :param filename: Path of the file on the filesystem
        :param callback: dict() that can be updated with progress data
        :param chunk_size: maximum size that can be posted at once
        :param file_part: if file is bigger that chunk_size, can be 1, 2, 3, etc...
        :return:
        """

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
        """
        Override parent method
        :return:int
        """
        return self.length

    def read(self, n=-1):
        """
        Override parent method to send the body in correct order
        :param n:int
        :return:data
        """
        transfer_rate = self.cursor//(time.clock() - self.start)
        if self.callback:
            try:
                self.callback(self.full_length, self.cursor * (self.file_part+1), transfer_rate)
            except Exception as e:
                logging.warning('Buffered reader callback error')
                return None
        dispatcher.send(signal=TRANSFER_RATE_SIGNAL, transfer_rate=transfer_rate)

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
    """
    Breaks up the multipart_encoded content into first and last part, to be able to "insert" the file content
    itself in-between
    :param fields: dict() fields to encode
    :return:(header_body, close_body, content_type)
    """
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
    """
    Upload a file with progress, file chunking if necessary, and stream content directly from file.
    :param url: url to post
    :param fields: dict() query parameters
    :param files: dict() {'fieldname' : '/path/to/file'}
    :param stream: whether to get response as stream or not
    :param with_progress: dict() updatable dict with progress data
    :param max_size: upload max size
    :return: response of the last requests if there were many of them
    """
    if with_progress:
        def cb(size=0, progress=0, rate=0):
            with_progress['progress'] = float(progress)/size*100
            with_progress['remaining_bytes'] = size - progress
            with_progress['transfer_rate'] = rate
            dispatcher.send(signal=TRANSFER_CALLBACK_SIGNAL, change=with_progress)
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
