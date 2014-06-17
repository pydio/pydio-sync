import io
import mock
import unittest

from pydio.sdk.utils import upload_file_showing_progress, BytesIOWithCallback


class UtilsLocalTest(unittest.TestCase):

    @mock.patch('requests.post', mock.Mock(return_value=True))
    def test_upload_file_showing_progress(self):
        url = 'http://127.0.0.1'
        files = {
            'userfile_0': ('my-name', io.BytesIO(b'test data').read())
        }
        data = {
            'force_post': 'true',
            'urlencoded_filename': 'file_name',
        }
        fields = dict(files, **data)
        auth = ('user', 'password')

        assert upload_file_showing_progress(url, fields, auth)

    def test_read_bytesio_with_callback(self):
        data = io.BytesIO(b'test data').read()
        data_len = len(data)
        mocked_callback = mock.Mock(return_value=None)

        body = BytesIOWithCallback(data, mocked_callback)
        body.read(1)
        body.read(1)
        body.read(1)

        assert mocked_callback.called
        assert mocked_callback.call_args_list == [
            mock.call(data_len, 0),
            mock.call(data_len, 1),
            mock.call(data_len, 2),
        ]
        assert mocked_callback.call_count == 3


if __name__ == '__main__':
    unittest.main()