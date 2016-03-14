#
# Copyright 2007-2014 Charles du Jeu - Abstrium SAS <team (at) pyd.io>
# This file is part of Pydio.
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
import os
import logging
import shutil
try:
    from pydio.utils.global_config import ConfigManager
    from pydio.utils.pydio_profiler import pydio_profile
    from pydio.utils import i18n
    _ = i18n.language.ugettext
except ImportError:
    from utils.global_config import ConfigManager
    from utils.pydio_profiler import pydio_profile
    from utils import i18n
    _ = i18n.language.ugettext

class ChangeProcessor:
    def __init__(self, change, change_store, job_config, local_sdk, remote_sdk, status_handler, event_logs_handler):
        """
        :param change: dict
        :param change_store: pydio.job.change_stores.SqliteChangeStore
        :param job_config: dict
        :param local_sdk: pydio.sdk.local.SystemSdk
        :param status_handler: pydio.local.status_handler
        :param event_logs_handler: pydio.job.EventLogger
        :type remote_sdk: pydio.sdk.remote.PydioSdk
        """
        self.job_config = job_config
        self.local_sdk = local_sdk
        self.remote_sdk = remote_sdk
        self.status_handler = status_handler
        self.log_handler = event_logs_handler
        self.change_store = change_store
        self.change = change

    def log(self, type, action, status, message, console_message, source='', target=''):
        logging.info(console_message)
        logging.info(message)
        self.log_handler.log(event_type=type, action=action, status=status, source=source, target=target, message=message)

    def update_node_status(self, path, status):
        self.status_handler.update_node_status(path, status)

    @pydio_profile
    def process_change(self):
        """
        Process the "change"
        :return:
        """
        item = self.change
        location = item['location']
        item['progress'] = 0
        if self.job_config.direction == 'up' and location == 'remote':
            return
        if self.job_config.direction == 'down' and location == 'local':
            return

        if item['type'] == 'create' or item['type'] == 'content':

            if item['node']['md5'] == 'directory':
                if item['node']['node_path']:
                    logging.debug('[' + location + '] Create folder ' + item['node']['node_path'])
                    if location == 'remote':
                        self.process_local_mkdir(item['node']['node_path'])
                    else:
                        self.process_remote_mkdir(item['node']['node_path'])
                    self.change_store.buffer_real_operation(location, item['type'], 'NULL', item['node']['node_path'])

            elif item['node']['bytesize'] == 0:
                logging.debug('[' + location + '] Create file ' + item['node']['node_path'])
                if location == 'remote':
                    self.process_local_mkfile(item['node']['node_path'])
                else:
                    self.process_remote_mkfile(item['node']['node_path'])
                self.change_store.buffer_real_operation(location, 'create', 'NULL', item['node']['node_path'])

            else:
                if item['node']['node_path']:
                    if location == 'remote':
                        self.process_download(item['node']['node_path'], is_mod=(item['type'] != 'create'), callback_dict=item)
                        if item['type'] == 'create':
                            self.change_store.buffer_real_operation(location, item['type'], 'NULL',
                                                                    item['node']['node_path'])
                        else:
                            self.change_store.buffer_real_operation(location, item['type'], item['node']['node_path'],
                                                                    item['node']['node_path'])
                    else:
                        self.process_upload(item['node']['node_path'], is_mod=(item['type'] != 'create'), callback_dict=item)
                        self.change_store.buffer_real_operation(location, item['type'], ('NULL' if item['type'] =='create' else item['node']['node_path']),
                                                                item['node']['node_path'])

        elif item['type'] == 'delete':
            logging.debug('[' + location + '] Should delete ' + item['source'])
            if location == 'remote':
                self.process_local_delete(item['source'])
            else:
                self.process_remote_delete(item['source'])
            self.change_store.buffer_real_operation(location, 'delete', item['source'], 'NULL')

        elif item['type'] == 'bulk_mkdirs':
            try:
                self.process_remote_bulk_mkdir(item['pathes'])
                bulk_location = item['location']
                bulk = list()
                for path in item['pathes']:
                    #self.change_store.buffer_real_operation(bulk_location, 'create', 'NULL', path)
                    bulk.append({'type':'create', 'location':bulk_location, 'source':'NULL', 'target':path})

                if bulk:
                    self.change_store.bulk_buffer_real_operation(bulk)
            except Exception as e:
                logging.exception(e)
                pass
        else:
            logging.debug('[' + location + '] Should move ' + item['source'] + ' to ' + item['target'])
            if location == 'remote':
                if os.path.exists(self.job_config.directory + item['source']):
                    if self.process_local_move(item['source'], item['target']):
                        self.change_store.buffer_real_operation(location, item['type'], item['source'], item['target'])
                else:
                    if item["node"]["md5"] == "directory":
                        logging.debug('Cannot find folder to move, switching to creation')
                        self.process_local_mkdir(item['target'])
                        self.change_store.buffer_real_operation(location, 'create', 'NULL', item['target'])
                    else:
                        logging.debug('Cannot find source, switching to DOWNLOAD')
                        self.process_download(item['target'], is_mod=False, callback_dict=item)
                    self.change_store.buffer_real_operation(location, 'create', 'NULL', item['target'])
            else:
                if self.remote_sdk.stat(item['source']):
                    self.process_remote_move(item['source'], item['target'])
                    self.change_store.buffer_real_operation(location, item['type'], item['source'], item['target'])
                elif item['node']['md5'] != 'directory':
                    logging.debug('Cannot find source, switching to UPLOAD')
                    self.process_upload(item['target'], callback_dict=item, is_mod=False)
                    self.change_store.buffer_real_operation(location, 'create', 'NULL', item['target'])

    def process_local_mkdir(self, path):
        message = path + ' <============ MKDIR'
        if not os.path.exists(self.job_config.directory + path):
            os.makedirs(self.job_config.directory + path)
        self.log(type='local', action='mkdir', status='success',
                 target=path, console_message=message, message=(_('New folder created at %s') % path))

    def process_remote_mkdir(self, path):
        message = 'MKDIR ============> ' + path
        self.remote_sdk.mkdir(path)
        self.log(type='remote', action='mkdir', status='success', target=path,
                 console_message=message, message=(_('Folder created at %s') % path))

    def process_remote_bulk_mkdir(self, pathes):
        self.remote_sdk.bulk_mkdir(pathes)
        for path in pathes:
            message = 'MKDIR ============> ' + path
            self.log(type='remote', action='mkdir', status='success', target=path,
                     console_message=message, message=(_('Folder created at %s') % path))

    def process_local_delete(self, path):
        if os.path.isdir(self.job_config.directory + path):
            self.local_sdk.rmdir(path)
            message = path + ' <============ DELETE'
            self.log(type='local', action='delete_folder', status='success',
                     target=path, message='Deleted folder ' + path, console_message=message)
        elif os.path.isfile(self.job_config.directory + path):
            os.unlink(self.job_config.directory + path)
            message = path + ' <============ DELETE'
            self.log(type='local', action='delete_file', status='success',
                     target=path, console_message=message, message=(_('Deleted file %s') % path))

    def process_remote_delete(self, path):
        self.remote_sdk.delete(path)
        message = 'DELETE ============> ' + path
        self.log(type='remote', action='delete', status='success',
                 target=path, console_message=message, message=(_('Folder %s deleted') % path))

    @pydio_profile
    def process_local_move(self, source, target):
        if os.path.exists(self.job_config.directory + source):
            if not os.path.exists(self.job_config.directory + os.path.dirname(target)):
                os.makedirs(self.job_config.directory + os.path.dirname(target))
            shutil.move(self.job_config.directory + source, self.job_config.directory + target)
            message = source + ' to ' + target + ' <============ MOVE'
            self.log(type='local', action='move', status='success', target=target,
                     source=source, console_message=message,
                     message=(_('Moved %(source)s to %(target)s') % ({'source': source, 'target': target})))
            return True
        return False

    @pydio_profile
    def process_remote_move(self, source, target):
        message = 'MOVE ============> ' + source + ' to ' + target
        self.update_node_status(target, 'IDLE')
        self.log(type='remote', action='move', status='success', target=target,
                 source=source, console_message=message,
                 message=(_('Moved %(source)s to %(target)s') % ({'source': source, 'target': target})))
        self.remote_sdk.rename(source, target)

    @pydio_profile
    def process_download(self, path, is_mod=False, callback_dict=None):
        self.update_node_status(path, 'DOWN')
        full_path = self.job_config.directory + path
        message = path + ' <====DOWNLOAD==== ' + path
        if is_mod and self.remote_sdk.is_rsync_supported() and ConfigManager.Instance().get_rdiff_path():
            sig_path = os.path.join(os.path.dirname(full_path), "." + os.path.basename(path)+".signature")
            delta_path = os.path.join(os.path.dirname(full_path), "." + os.path.basename(path)+".delta")
            try:
                self.local_sdk.rsync_signature(full_path, sig_path)
                self.remote_sdk.rsync_delta(path, sig_path, delta_path)
                self.local_sdk.rsync_patch(full_path, delta_path)
                message = path + ' <====PATCH====== ' + path
            except Exception as e:
                logging.exception(e)
                self.remote_sdk.stat_and_download(path, self.job_config.directory + path, callback_dict)
            if os.path.exists(sig_path):
                os.remove(sig_path)
            if os.path.exists(delta_path):
                os.remove(delta_path)
        else:
            self.remote_sdk.stat_and_download(path, self.job_config.directory + path, callback_dict)

        self.update_node_status(path, 'IDLE')
        self.log(type='local', action='download', status='success',
                 target=path, console_message=message, message=(_('File %s downloaded from server') % path))

    @pydio_profile
    def process_upload(self, path, is_mod=False, callback_dict=None):
        self.update_node_status(path, 'UP')
        max_upload_size = -1
        if self.job_config.server_configs and 'UPLOAD_MAX_SIZE' in self.job_config.server_configs:
            max_upload_size = int(self.job_config.server_configs['UPLOAD_MAX_SIZE'])

        full_path = self.job_config.directory + path
        message = path + ' =====UPLOAD====> ' + path
        if is_mod and self.remote_sdk.is_rsync_supported() and ConfigManager.Instance().get_rdiff_path():
            sig_path = os.path.join(os.path.dirname(full_path), "." + os.path.basename(path)+".signature")
            delta_path = os.path.join(os.path.dirname(full_path), "." + os.path.basename(path)+".delta")
            try:
                self.remote_sdk.rsync_signature(path, sig_path)
                self.local_sdk.rsync_delta(full_path, sig_path, delta_path)
                self.remote_sdk.rsync_patch(path, delta_path)
                message = path + ' =====PATCH=====> ' + path
            except Exception as e:
                logging.exception(e)
                self.remote_sdk.upload_and_hashstat(full_path, self.local_sdk.stat(path), path, self.status_handler,
                                                    callback_dict, max_upload_size=max_upload_size)
            finally:
                if os.path.exists(sig_path):
                    os.remove(sig_path)
                if os.path.exists(delta_path):
                    os.remove(delta_path)
        else:
            self.remote_sdk.upload_and_hashstat(full_path, self.local_sdk.stat(path), path, self.status_handler,
                                callback_dict, max_upload_size=max_upload_size)

        self.update_node_status(path, 'IDLE')
        self.log(type='remote', action='upload', status='success', target=path,
                 console_message=message, message=(_('File %s uploaded to server') % path))

    def process_local_mkfile(self, path):
        message = path + ' <============ MKFILE'
        self.local_sdk.mkfile(path)
        self.log(type='local', action='mkfile', status='success', target=path, console_message=message, message=(_('New file created at %s') % path))

    def process_remote_mkfile(self, path):
        message = 'MKFILE ============> ' + path
        self.remote_sdk.mkfile(path, self.local_sdk.stat(path))
        self.log(type='remote', action='mkfile', status='success', target=path,
                 console_message=message, message=(_('File created at %s') % path))


class StorageChangeProcessor(ChangeProcessor):

    @pydio_profile
    def process_change(self):
        """
        Process the "change" by just sending an lsync command to server
        :return:
        """
        item = self.change
        location = item['location']
        item['progress'] = 0
        if location == 'remote':
            # Just ignore all remote changes
            return

        if item['type'] == 'create' or item['type'] == 'content':

            if item['node']['md5'] == 'directory':
                if item['node']['node_path']:
                    logging.debug('[' + location + '] Create folder ' + item['node']['node_path'])
                    self.remote_sdk.lsync(target=item['node']['node_path'])
                    self.change_store.buffer_real_operation(location, item['type'], 'NULL', item['node']['node_path'])

            elif item['node']['bytesize'] == 0:
                logging.debug('[' + location + '] Create file ' + item['node']['node_path'])
                self.remote_sdk.lsync(target=item['node']['node_path'])
                self.change_store.buffer_real_operation(location, 'create', 'NULL', item['node']['node_path'])

            else:
                if item['node']['node_path']:
                    self.remote_sdk.lsync(target=item['node']['node_path'])
                    self.change_store.buffer_real_operation(location, item['type'], ('NULL' if item['type'] =='create' else item['node']['node_path']),
                                                            item['node']['node_path'])

        elif item['type'] == 'delete':
            logging.debug('[' + location + '] Should delete ' + item['source'])
            self.remote_sdk.lsync(source=item['source'])
            self.change_store.buffer_real_operation(location, 'delete', item['source'], 'NULL')

        elif item['type'] == 'bulk_mkdirs':
            try:
                bulk_location = item['location']
                bulk = list()
                for path in item['pathes']:
                    self.remote_sdk.lsync(target=path)
                    bulk.append({'type': 'create', 'location': bulk_location, 'source':'NULL', 'target': path})

                if bulk:
                    self.change_store.bulk_buffer_real_operation(bulk)
            except Exception as e:
                logging.exception(e)
                pass
        else:
            logging.debug('[' + location + '] Should move ' + item['source'] + ' to ' + item['target'])
            self.remote_sdk.lsync(source=item['source'], target=item['target'])
            self.change_store.buffer_real_operation(location, item['type'], item['source'], item['target'])
