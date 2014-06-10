#
# Copyright 2007-2014 Charles du Jeu - Abstrium SAS <team (at) pyd.io>
# This file is part of Pydio.
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
import os
import logging


class ChangeProcessor:
    def __init__(self, change, change_store, job_config, local_sdk, remote_sdk, status_handler, event_logs_handler):
        self.job_config = job_config
        self.local_sdk = local_sdk
        self.remote_sdk = remote_sdk
        self.status_handler = status_handler
        self.log_handler = event_logs_handler
        self.change_store = change_store
        self.change = change

    def log(self, type, action, status, message, console_message, source='', target=''):
        logging.info(console_message)
        self.log_handler.log(type=type, action=action, status=status, source=source, target=target, message=message)

    def update_node_status(self, path, status):
        self.status_handler.update_node_status(path, status)

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
            else:
                if item['node']['node_path']:
                    if location == 'remote':
                        self.process_download(item['node']['node_path'], callback_dict=item)
                        if item['type'] == 'create':
                            self.change_store.buffer_real_operation(location, item['type'], 'NULL',
                                                                    item['node']['node_path'])
                        else:
                            self.change_store.buffer_real_operation(location, item['type'], item['node']['node_path'],
                                                                    item['node']['node_path'])
                    else:
                        self.process_upload(item['node']['node_path'], item)
                        self.change_store.buffer_real_operation(location, item['type'], 'NULL',
                                                                item['node']['node_path'])

        elif item['type'] == 'delete':
            logging.debug('[' + location + '] Should delete ' + item['source'])
            if location == 'remote':
                self.process_local_delete(item['source'])
            else:
                self.process_remote_delete(item['source'])
            self.change_store.buffer_real_operation(location, 'delete', item['source'], 'NULL')

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
                        self.process_download(item['target'], callback_dict=item)
                    self.change_store.buffer_real_operation(location, 'create', 'NULL', item['target'])
            else:
                if self.remote_sdk.stat(item['source']):
                    self.process_remote_move(item['source'], item['target'])
                    self.change_store.buffer_real_operation(location, item['type'], item['source'], item['target'])
                elif item['node']['md5'] != 'directory':
                    logging.debug('Cannot find source, switching to UPLOAD')
                    self.process_upload(item['target'], item)
                    self.change_store.buffer_real_operation(location, 'create', 'NULL', item['target'])


    def process_local_mkdir(self, path):
        message = path + ' <============ MKDIR'
        os.makedirs(self.job_config.directory + path)
        self.log(type='local', action='mkdir', status='success',
                 target=path, console_message=message, message=('New folder created at %s' % path))

    def process_remote_mkdir(self, path):
        message = 'MKDIR ============> ' + path
        self.remote_sdk.mkdir(path)
        self.log(type='remote', action='mkdir', status='success', target=path,
                 console_message=message, message=('Folder created at %s' % path))

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
                     target=path, console_message=message, message='Deleted file ' + path)

    def process_remote_delete(self, path):
        self.remote_sdk.delete(path)
        message = 'DELETE ============> ' + path
        self.log(type='remote', action='delete', status='success',
                 target=path, console_message=message, message=('Folder %s deleted' % path))

    def process_local_move(self, source, target):
        if os.path.exists(self.job_config.directory + source):
            if not os.path.exists(self.job_config.directory + os.path.dirname(target)):
                os.makedirs(self.job_config.directory + os.path.dirname(target))
            os.rename(self.job_config.directory + source, self.job_config.directory + target)
            message = source + ' to ' + target + ' <============ MOVE'
            self.log(type='local', action='move', status='success', target=target,
                     source=source, console_message=message, message=('Moved %s to %s' % (source, target)))
            return True
        return False

    def process_remote_move(self, source, target):
        message = 'MOVE ============> ' + source + ' to ' + target
        self.log(type='remote', action='move', status='success', target=target,
                 source=source, console_message=message, message=('Moved %s to %s' % (source, target)))
        self.remote_sdk.rename(source, target)

    def process_download(self, path, callback_dict=None):
        self.update_node_status(path, 'DOWN')
        self.remote_sdk.download(path, self.job_config.directory + path, callback_dict)
        self.update_node_status(path, 'IDLE')
        message = path + ' <=============== ' + path
        self.log(type='local', action='download', status='success',
                 target=path, console_message=message, message=('File %s downloaded from server' % path))

    def process_upload(self, path, callback_dict=None):
        self.update_node_status(path, 'UP')
        max_upload_size = -1
        if self.job_config.server_configs and 'UPLOAD_MAX_SIZE' in self.job_config.server_configs:
            max_upload_size = int(self.job_config.server_configs['UPLOAD_MAX_SIZE'])
        self.remote_sdk.upload(self.job_config.directory + path, self.local_sdk.stat(path), path, callback_dict,
                               max_upload_size=max_upload_size)
        self.update_node_status(path, 'IDLE')
        message = path + ' ===============> ' + path
        self.log(type='remote', action='upload', status='success', target=path,
                 console_message=message, message=('File %s uploaded to server' % path))
