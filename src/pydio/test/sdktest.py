#
#  Copyright 2007-2014 Charles du Jeu - Abstrium SAS <team (at) pyd.io>
#  This file is part of Pydio.
#
#  Pydio is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#
#  Pydio is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with Pydio.  If not, see <http://www.gnu.org/licenses/>.
#
#  The latest code can be found at <http://pyd.io/>.
#

from pydio.sdkremote.remote import PydioSdk
import unittest

class SdkTest(unittest.TestCase):
    """ Run me with python sdktest.py
    """
    def __init__(self, url='', basepath='', ws_id='', user_id='', auth=()):
        self.sdk = PydioSdk(url, basepath, ws_id, user_id, auth)

    def test_set_server_configs(self, configs):
        return False
    
    def test_set_interrupt(self):
        return False
    def test_remove_interrupt(self):
        return False
    def test_urlencode_normalized(self, unicode_path):
        return False
    def test_normalize(self, unicode_path):
        return False
    def test_normalize_reverse(self, unicode_path):
        return False
    def test_set_tokens(self, tokens):
        return False
    def test_get_tokens(self):
        return False
    def test_basic_authenticate(self):
        return False
    def test_perform_basic(self, url, request_type='get', data=None, files=None, headers=None, stream=False, with_progress=False):
        return False
    def test_perform_with_tokens(self, token, private, url, request_type='get', data=None, files=None, headers=None, stream=False, with_progress=False):
        return False
    def test_perform_request(self, url, type='get', data=None, files=None, headers=None, stream=False, with_progress=False):
        return False
    def test_check_basepath(self):
        return False
    def test_changes(self, last_seq):
        return False
    def test_changes_stream(self, last_seq, callback):
        return False
    def test_stat(self, path, with_hash=False, partial_hash=None):
        return False
    def test_bulk_stat(self, pathes, result=None, with_hash=False):
        return False
    def test_mkdir(self, path):
        return False
    def test_bulk_mkdir(self, pathes):
        return False
    def test_mkfile(self, path):
        return False
    def test_rename(self, source, target):
        return False
    def test_lsync(self, source=None, target=None, copy=False):
        return False
    def test_delete(self, path):
        return False
    def test_load_server_configs(self):
        return False
    def test_upload_and_hashstat(self, local, local_stat, path, callback_dict=None, max_upload_size=-1):
        return False
    def test_upload(self, local, local_stat, path, callback_dict=None, max_upload_size=-1):
        return False
    def test_stat_and_download(self, path, local, callback_dict=None):
        return False
    def test_download(self, path, local, callback_dict=None):
        return False
    def test_list(self, dir=None, nodes=list(), options='al', recursive=False, max_depth=1, remote_order='', order_column='', order_direction='', max_nodes=0, call_back=None):
        return False
    def test_snapshot_from_changes(self, call_back=None):
        return False
    def test_apply_check_hook(self, hook_name='', hook_arg='', file='/'):
        return False
    def test_quota_usage(self):
        return False
    def test_has_disk_space_for_upload(self, path, file_size):
        return False
    def test_is_pydio_error_response(self, resp):
        return False
    def test_rsync_delta(self, path, signature, delta_path):
        return False
    def test_rsync_signature(self, path, signature):
        return False
    def test_rsync_patch(self, path, delta_path):
        return False
    def test_is_rsync_supported(self):
        return False
    def test_upload_file_with_progress(self, url, fields, files, stream, with_progress, max_size=0, auth=None):
        return False
    def test_check_share_link(self, file_name):
        return False
    def test_share(self, ws_label, ws_description, password, expiration, downloads, can_read, can_download, paths,link_handler, can_write):
        return False
    def test_unshare(self, path):
        return False

if __name__ == "__main__":
    unittest.main()