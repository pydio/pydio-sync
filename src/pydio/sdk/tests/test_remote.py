import io
import json
import keyring
import mock
import random
import requests
import time
import unittest
from requests.packages.urllib3 import response

from pydio.sdk.exceptions import (
    PydioSdkTokenAuthException,
    PydioSdkBasicAuthException,
    PydioSdkException
)
from pydio.sdk.remote import PydioSdk


class RemoteSdkLocalTests(unittest.TestCase):

    @mock.patch('keyring.get_password')
    def setUp(self, mock_get):
        mock_get.return_value = ('user_id', 'passwd')
        self.sdk = PydioSdk(
            'url',
            'basepath',
            'ws_id',
            'user_id',
            'auth'
        )

    @mock.patch.object(keyring, 'set_password')
    @mock.patch.object(json, 'loads')
    @mock.patch.object(requests, 'get')
    def test_basic_authenticate(self, mock_get, mock_loads, mock_set):
        resp = mock.Mock(spec=response)
        resp.status_code = 401

        resp_ok = mock.Mock(spec=response)
        resp_ok.status_code = 200
        resp_ok.content = ''

        mock_get.side_effect = [resp, resp_ok, resp_ok]
        tokens = {'t': '123', 'p': '456'}
        mock_loads.side_effect = [ValueError, tokens]

        self._basic_authenticate_auth_exception_thrown()
        self._basic_authenticate_auth_json_loads_value_error()
        self._basic_authenticate_tokens_returned(mock_set, tokens)

    def _basic_authenticate_auth_exception_thrown(self):
        try:
            self.sdk.basic_authenticate()
        except PydioSdkBasicAuthException as e:
            assert e.message == 'Http-Basic authentication failed, wrong credentials?'
        else:
            assert False

    def _basic_authenticate_auth_json_loads_value_error(self):
        assert not self.sdk.basic_authenticate()

    def _basic_authenticate_tokens_returned(self, mock_set, tokens):
        assert set(self.sdk.basic_authenticate()) == set(tokens)
        assert mock_set.call_args_list == [
            mock.call('url/api/basepath', 'user_id-token', '123:456')
        ]

    @mock.patch.object(random, 'random')
    @mock.patch.object(requests, 'get')
    def test_perform_with_token_get(self, mock_get, mock_random):
        resp_ok = mock.Mock(spec=response)
        resp_ok.status_code = 200
        mock_get.return_value = resp_ok
        mock_random.return_value = 5

        auth_hash = ':'.join(
            [
                'ac3478d69a3c81fa62e60f5c3696165a4e5e6ac4',
                '15d73c0dfd7be6df4c135ec405b46c13e619da76ca094279a9b2bb6be0c18327',
            ])

        test_data = [
            {'url': 'http://url', 'sign': '?'},
            {'url': 'http://url?param=1', 'sign': '&'},
        ]

        for data in test_data:
            assert self.sdk.perform_with_tokens('token', 'private', data['url'])
            assert mock_get.call_args_list == [
                mock.call(
                    url=''.join(
                        [
                            data['url'],
                            data['sign'],
                            'auth_token=token&auth_hash=',
                            auth_hash,
                        ]),
                    stream=False)
            ]
            mock_get.call_args_list = []

    @mock.patch.object(random, 'random')
    @mock.patch.object(requests, 'post')
    @mock.patch('pydio.sdk.remote.upload_file_showing_progress')
    def test_perform_with_token_post(self, mock_upload, mock_post, mock_random):
        resp = mock.Mock(spec=response)
        resp.status_code = 200
        mock_post.return_value = resp
        mock_upload.return_value = resp
        mock_random.return_value = 5

        auth_hash = ':'.join(
            [
                'ac3478d69a3c81fa62e60f5c3696165a4e5e6ac4',
                '15d73c0dfd7be6df4c135ec405b46c13e619da76ca094279a9b2bb6be0c18327',
            ])

        test_data = [
            {
                'with_progress': True,
                'files': {'file1': 'name1'},
                'upload_args': [
                    mock.call(
                        'http://url',
                        {'auth_hash': auth_hash, 'file1': 'name1', 'auth_token': 'token'},
                        False
                    )
                ],
                'post_args': [],
            },
            {
                'with_progress': False,
                'files': {'file1': 'name1'},
                'upload_args': [],
                'post_args': [
                    mock.call(
                        files={'file1': 'name1'},
                        url='http://url',
                        data={'auth_hash': auth_hash, 'auth_token': 'token'},
                        stream=False,
                    )
                ],
            },
            {
                'with_progress': False,
                'files': None,
                'upload_args': [],
                'post_args': [
                    mock.call(
                        url='http://url',
                        data={'auth_hash': auth_hash, 'auth_token': 'token'},
                        stream=False,
                    )
                ]
            },
        ]

        for data in test_data:
            assert self.sdk.perform_with_tokens(
                'token',
                'private',
                'http://url',
                type='post',
                files=data['files'],
                with_progress=data['with_progress'],
            )
            assert mock_upload.called == data['with_progress']
            assert mock_post.called == (not data['with_progress'])

            mock_upload.called = False
            mock_post.called = False

            assert mock_upload.call_args_list == data['upload_args']
            assert mock_post.call_args_list == data['post_args']

            mock_upload.call_args_list = []
            mock_post.call_args_list = []

    @mock.patch.object(PydioSdkTokenAuthException, '__init__')
    @mock.patch.object(requests, 'get')
    def test_perform_with_token_exception_raised(self, mock_get, mock_init):
        resp = mock.Mock(spec=response)
        resp.status_code = 401
        mock_get.return_value = resp
        mock_init.return_value = None

        test_data = [
            {
                'method_type': 'other',
                'exception_init_param': 'Unsupported HTTP method',
            },
            {
                'method_type': 'get',
                'exception_init_param': 'Authentication Exception',
            },
        ]

        for data in test_data:
            try:
                self.sdk.perform_with_tokens(
                    'token',
                    'private',
                    'http://url',
                    type=data['method_type']
                )
            except:
                assert mock_init.call_args_list == [
                    mock.call(data['exception_init_param'])
                ]
            else:
                assert False

            mock_init.call_args_list = []

    @mock.patch.object(PydioSdk, 'basic_authenticate')
    @mock.patch.object(keyring, 'get_password')
    @mock.patch.object(PydioSdk, 'perform_with_tokens')
    def test_perform_request(self, mock_perform, mock_get, mock_basic):
        resp = mock.Mock(spec=response)
        resp.status_code = 200

        mock_get.side_effect = [None, 'test:password', 'test:password']
        mock_basic.return_value = {'t': 'test', 'p': 'password'}
        mock_perform.side_effect = [resp, resp, PydioSdkTokenAuthException('test'), resp]

        test_data = [
            {
                'basic_auth_called': True,
                'perform_call_args': mock.call('test', 'password', 'http://url', 'get', None, None, False)
            },
            {
                'basic_auth_called': False,
                'perform_call_args': mock.call('test', 'password', 'http://url', 'get', None, None, False, False)
            },
            {
                'basic_auth_called': True,
                'perform_call_args': mock.call('test', 'password', 'http://url', 'get', None, None, False)
            },
        ]

        for data in test_data:
            self.sdk.perform_request('http://url')
            assert mock_basic.called == data['basic_auth_called']
            assert mock_perform.call_args == data['perform_call_args']
            mock_basic.called = False
            mock_perform.call_args_list = []

    @mock.patch.object(PydioSdk, 'perform_request')
    def test_changes_valid_json(self, mock_perform):
        resp = mock.Mock(spec=response)
        resp.content = '["foo", {"bar":["baz", null, 1.0, 2]}]'
        mock_perform.return_value = resp

        assert self.sdk.changes(555) == json.loads(resp.content)
        assert mock_perform.call_args == mock.call(
            url='url/api/basepath/changes/555?filter=ws_id'
        )

    @mock.patch.object(PydioSdk, 'perform_request')
    def test_changes_invalid_json_exception_raised(self, mock_perform):
        resp = mock.Mock(spec=response)
        resp.content = '["foo", {"bar"["baz", null, 1.0, 2]}]'
        mock_perform.return_value = resp
        exception_message = 'Invalid JSON value received while getting remote changes'

        with self.assertRaises(Exception) as context:
            self.sdk.changes(555)
            assert context.exception.message == exception_message

    @mock.patch.object(PydioSdk, 'perform_request')
    def test_stat(self, mock_perform):
        resp = mock.Mock(spec=response)
        test_data = [
            {
                'content': '["size", {"bar":["baz", null, 1.0, 2]}]',
                'result': json.loads('["size", {"bar":["baz", null, 1.0, 2]}]'),
            },
            {
                'content': '["foo", {"bar":["baz", null, 1.0, 2]}]',
                'result': False,
            },
            {
                'content': '',
                'result': False,
            },
        ]

        for data in test_data:
            resp.content = data['content']
            mock_perform.return_value = resp
            assert self.sdk.stat('/path') == data['result']

        assert mock_perform.call_args_list[0] == mock_perform.call_args_list[1]
        assert mock_perform.call_args_list[1] == mock_perform.call_args_list[2]
        assert mock_perform.call_args_list[2] == mock.call(
            'url/api/basepath/statws_id/path'
        )

    @mock.patch.object(PydioSdk, 'perform_request')
    def test_stat_exception_raised(self, mock_perform):
        errors_thrown = [ValueError, Exception]
        mock_perform.side_effect = errors_thrown

        for error in errors_thrown:
            with self.assertRaises(error):
                assert not self.sdk.changes(555)

    @mock.patch.object(PydioSdk, 'perform_request')
    def test_bulk_stat(self, mock_perform):
        resp = mock.Mock(spec=response)
        resp.content = '["foo", {"bar":["baz", null, 1.0, 2]}]'
        mock_perform.return_value = resp
        result_string = ''.join(['{"/path1": ', resp.content, '}'])
        result = json.loads(result_string)

        assert self.sdk.bulk_stat(['/path1']) == result
        assert mock_perform.call_args == mock.call(
            'url/api/basepath/statws_id/path1',
            type='post',
            data={'nodes[]': ['ws_id/path1']}
        )

    @mock.patch.object(json, 'loads')
    @mock.patch.object(PydioSdk, 'perform_request')
    def test_bulk_stat_exception_raised(self, mock_perform, mock_loads):
        resp = mock.Mock(spec=response)
        resp.content = '["foo", {"bar":["baz", null, 1.0, 2]}]'
        mock_perform.return_value = resp
        mock_loads.side_effect = ValueError

        with self.assertRaises(Exception):
            self.sdk.bulk_stat(['/path'])

    @mock.patch.object(PydioSdk, 'perform_request')
    def test_mkdir(self, mock_perform):
        resp = mock.Mock(spec=response)
        resp.content = '["foo", {"bar":["baz", null, 1.0, 2]}]'
        mock_perform.return_value = resp

        assert self.sdk.mkdir('/path') == resp.content
        assert mock_perform.call_args == mock.call(
            url='url/api/basepath/mkdirws_id/path'
        )

    @mock.patch.object(PydioSdk, 'perform_request')
    def test_mkfile(self, mock_perform):
        resp = mock.Mock(spec=response)
        resp.content = '["foo", {"bar":["baz", null, 1.0, 2]}]'
        mock_perform.return_value = resp

        assert self.sdk.mkfile('/path') == resp.content
        assert mock_perform.call_args == mock.call(
            url='url/api/basepath/mkfilews_id/path'
        )

    @mock.patch.object(PydioSdk, 'perform_request')
    def test_rename(self, mock_perform):
        resp = mock.Mock(spec=response)
        resp.content = '["foo", {"bar":["baz", null, 1.0, 2]}]'
        mock_perform.return_value = resp

        called_with_arguments = [
            mock.call(
                url='url/api/basepath/rename',
                type='post',
                data={'dest': 'ws_id/target', 'file': 'ws_id/source'}
            ),
            mock.call(
                url='url/api/basepath/rename',
                type='post',
                data={'dest': 'ws_id/test', 'file': 'ws_id/test'}
            )
        ]

        assert self.sdk.rename('/source', '/target') == resp.content
        assert self.sdk.rename('/test', '/test') == resp.content
        assert mock_perform.call_args_list == called_with_arguments

    @mock.patch.object(PydioSdk, 'perform_request')
    def test_delete(self, mock_perform):
        resp = mock.Mock(spec=response)
        resp.content = '["foo", {"bar":["baz", null, 1.0, 2]}]'
        mock_perform.return_value = resp

        assert self.sdk.delete('/path') == resp.content
        assert mock_perform.call_args == mock.call(
            url='url/api/basepath/deletews_id/path'
        )

    @mock.patch('__builtin__.open')
    @mock.patch.object(PydioSdk, 'perform_request')
    @mock.patch.object(PydioSdk, 'mkfile')
    @mock.patch.object(PydioSdk, 'stat')
    def test_upload_exception_raised(self, mock_stat, mock_mkfile, mock_perform, mock_open):
        mock_open.read = io.BytesIO(b'test data').read()

        test_data = [
            {
                'local': None,
                'local_stat': None,
                'exception_message': '[sdk operation] [upload] /tmp (local file to upload not found!)',
                'mkfile_called': False,
                'stat_side_effect': [{'size': 1}],
            },
            {
                'local': None,
                'local_stat': {'size': 0},
                'exception_message':
                '[sdk operation] [upload] /tmp (File not correct after upload (expected size was 0 bytes))',
                'mkfile_called': True,
                'stat_side_effect': None,
            },
            {
                'local': '/tmp',
                'local_stat': {'size': 1},
                'exception_message':
                '[sdk operation] [upload] /tmp (File not correct after upload)',
                'mkfile_called': False,
                'stat_side_effect': [{'size': 0}, None],
            },
        ]

        for data in test_data:
            mock_stat.side_effect = data['stat_side_effect']
            try:
                self.sdk.upload(None, data['local_stat'], '/tmp')
            except PydioSdkException, e:
                assert e.message == data['exception_message']
            else:
                assert False

            assert mock_mkfile.called == data['mkfile_called']
            mock_mkfile.called = False

    @mock.patch('__builtin__.open')
    @mock.patch.object(PydioSdk, 'perform_request')
    @mock.patch.object(PydioSdk, 'mkdir')
    @mock.patch.object(PydioSdk, 'mkfile')
    @mock.patch.object(PydioSdk, 'stat')
    def test_upload(self, mock_stat, mock_mkfile, mock_mkdir, mock_perform, mock_open):
        mock_open.read = io.BytesIO(b'test data').read()

        test_data = [
            {
                'local': None,
                'local_stat': {'size': 0},
                'path': '/tmp',
                'stat_side_effect': [{'size': 0}],
                'mkfile_called': True,
                'mkdir_called': False,
            },
            {
                'local': '/tmp',
                'local_stat': {'size': 1},
                'path': '/tmp',
                'stat_side_effect': [{'size': 1}],
                'mkfile_called': False,
                'mkdir_called': False,
            },
            {
                'local': '/tmp',
                'local_stat': {'size': 1},
                'path': '/tmp/dir/',
                'stat_side_effect': ['/folder', {'size': 1}],
                'mkfile_called': False,
                'mkdir_called': False,
            },
            {
                'local': '/tmp',
                'local_stat': {'size': 1},
                'path': '/tmp/dir/',
                'stat_side_effect': [None, {'size': 1}],
                'mkfile_called': False,
                'mkdir_called': True,
            },
        ]

        for data in test_data:
            mock_stat.side_effect = data['stat_side_effect']
            assert self.sdk.upload(data['local'], data['local_stat'], data['path'])
            assert mock_mkfile.called == data['mkfile_called']
            assert mock_mkdir.called == data['mkdir_called']
            mock_mkfile.called = False
            mock_mkdir.called = False

    @mock.patch('os.stat')
    @mock.patch('os.path.exists')
    @mock.patch('os.unlink')
    @mock.patch('os.makedirs')
    @mock.patch('__builtin__.open')
    @mock.patch.object(PydioSdk, 'stat')
    def test_download_exception_raised(self, mock_stat, mock_open, mock_make, mock_unlink, mock_exists, mock_osstat):
        mock_make.return_value = True

        stat_result = mock.Mock(spec=requests.Response)
        stat_result.st_size = 0
        mock_osstat.return_value = stat_result

        test_data = [
            {
                'exception_message': '[sdk operation] [download] /tmp (Original not found on server)',
                'open': True,
                'stat': None,
                'exists': False,
            },
            {
                'exception_message': '[sdk operation] [download] /tmp (Error opening local file for writing)',
                'open': Exception,
                'stat': 'orig',
                'exists': True,
            },
            {
                'exception_message': '[sdk operation] [download] /tmp (Error opening local file for writing)',
                'open': True,
                'stat': 'orig',
                'exists': True,
            },
            {
                'exception_message': '[sdk operation] [download] /tmp (Error opening local file for writing)',
                'open': True,
                'stat': {'size': 0},
                'exists': True,
            },
        ]

        for data in test_data:
            mock_open.return_value = data['open']
            mock_stat.return_value = data['stat']
            mock_exists.return_value = data['exists']
            try:
                self.sdk.download('/tmp', 'local')
            except PydioSdkException, e:
                assert e.message == data['exception_message']
            else:
                assert False

    @mock.patch.object(time, 'clock')
    @mock.patch('os.stat')
    @mock.patch('os.rename')
    @mock.patch('os.path.exists')
    @mock.patch.object(PydioSdk, 'perform_request')
    @mock.patch.object(PydioSdk, 'stat')
    def test_download(self, mock_stat, mock_perform, mock_exists, mock_rename, mock_osstat, mock_clock):
        mock_stat.return_value = {'size': 0}
        mock_exists.return_value = True

        stat_result = mock.Mock(spec=requests.Response)
        stat_result.st_size = 0
        mock_osstat.return_value = stat_result

        test_data = [
            {'perform_headers': {'content-length': 2}, 'write_args': [mock.call('a'), mock.call('b')]},
            {'perform_headers': {'content-length': None}, 'write_args': [mock.call(['a', 'b'])]},
        ]

        for data in test_data:
            resp = mock.Mock()
            resp.headers = data['perform_headers']
            resp.content = ['a', 'b']
            resp.iter_content = lambda size: resp.content
            mock_perform.return_value = resp
            m = self.mock_open()
            with mock.patch('__builtin__.open', m, create=True):
                assert self.sdk.download('/tmp', 'local')
                h = m()
                assert h.write.call_args_list == data['write_args']
                assert mock_rename.called

    def mock_open(self, data=None):
        m = mock.MagicMock(spec=file)
        h = mock.MagicMock(spec=file)
        h.write.return_value = None

        if data is None:
            h.__enter__.return_value = h
        else:
            h.__enter__.return_value = data
        m.return_value = h
        return m


if __name__ == '__main__':
    unittest.main()
