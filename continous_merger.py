import time
import os
from requests.exceptions import ConnectionError
from localdb import LocalDbHandler
from sdk import PydioSdk, SystemSdk, ProcessException
import threading
import pickle
import logging
# -*- coding: utf-8 -*-


class ContinuousDiffMerger(threading.Thread):

    def __init__(self, local_path, remote_ws, sdk_url, sdk_user_id='', sdk_auth=()):
        threading.Thread.__init__(self)
        self.basepath = local_path
        self.ws_id = remote_ws
        if sdk_user_id:
            self.sdk = PydioSdk(sdk_url, basepath=local_path, ws_id=self.ws_id, user_id=sdk_user_id)
        else:
            self.sdk = PydioSdk(sdk_url, basepath=local_path, ws_id=self.ws_id, auth=sdk_auth)

        self.system = SystemSdk(local_path)
        self.remote_seq = 1
        self.local_seq = 0
        self.local_target_seq = 1
        self.remote_target_seq = 0
        self.local_seqs = []
        self.remote_seqs = []
        self.db_handler = LocalDbHandler(local_path)
        self.interrupt = False
        self.online_timer = 10
        self.offline_timer = 60
        self.online_status = True
        if os.path.exists("data/sequences"):
            sequences = pickle.load(open("data/sequences", "rb"))
            self.remote_seq = sequences['remote']
            self.local_seq = sequences['local']

    def stop(self):
        self.interrupt = True

    def run(self):
        while not self.interrupt:

            try:
                local_changes = dict(data=dict(), path_to_seqs=dict())
                remote_changes = dict(data=dict(), path_to_seqs=dict())
                logging.info('Loading remote changes with sequence ' + str(self.remote_seq))
                try:
                    self.remote_target_seq = self.get_remote_changes(self.remote_seq, remote_changes)
                except ConnectionError as ce:
                    logging.info('No connection detected, waiting to retry')
                    self.online_status = False
                    time.sleep(self.offline_timer)
                    continue
                self.online_status = True
                logging.info('Loading local changes with sequence ' + str(self.local_seq))
                self.local_target_seq = self.db_handler.get_local_changes(self.local_seq, local_changes)
                self.local_seqs = local_changes['data'].keys() #map(lambda x:x['seq'], local_changes)
                self.remote_seqs = remote_changes['data'].keys() #map(lambda x:x['seq'], remote_changes)
                logging.info('Reducing changes')
                changes = self.reduce_changes(local_changes, remote_changes)
                logging.info('Processing changes')
                for change in changes:
                    try:
                        self.process_change(change)
                        self.remove_seq(change['seq'], change['location'])
                    except ProcessException as pe:
                        logging.error(pe.message)
                    except OSError as e:
                        logging.error(e.message)
                    if self.interrupt:
                        break
                    time.sleep(0.5)
            except OSError as e:
                logging.error('Type Error! ')
            time.sleep(self.online_timer)

    def remove_seq(self, seq_id, location):
        if location == 'local':
            self.local_seqs.remove(seq_id)
            if len(self.local_seqs):
                self.local_seq = min(min(self.local_seqs), self.local_target_seq)
            else:
                self.local_seq = self.local_target_seq
        else:
            self.remote_seqs.remove(seq_id)
            if len(self.remote_seqs):
                self.remote_seq = min(min(self.remote_seqs), self.remote_target_seq)
            else:
                self.remote_seq = self.remote_target_seq
        pickle.dump(dict(
            local=self.local_seq,
            remote=self.remote_seq
        ), open('data/sequences', 'wb'))

    def stat_path(self, path, location, stats=None):
        try:
            if stats:
                return stats[path]
        except KeyError:
            pass

        if location == 'remote':
            return self.sdk.stat(path)
        else:
            return self.system.stat(path)
            pass

    def filter_change(self, item, my_stat=None, other_stats=None):

        location = item['location']
        opposite = 'local' if item['location'] == 'remote' else 'remote'
        res = False
        if item['type'] == 'create' or item['type'] == 'content':
            # If it does not exist on remote size, ok
            test_stat = self.stat_path(item['node']['node_path'], location=opposite, stats=other_stats)
            if not test_stat:
                return False
            # Do not create or update content if it does not actually exists
            #loc_stat = self.stat_corresponding_item(item['node']['node_path'], location=opposite, stats=my_stat)
            #if not loc_stat:
            #    res = True
            # If it exists but is a directory, it won't change
            if item['node']['md5'] == 'directory':
                res = True
            # If it exists and has same size, ok
            elif test_stat['size'] == item['node']['bytesize']: # WE SHOULD TEST MD5 HERE AS WELL!
                res = True
        elif item['type'] == 'delete':
            # Shall we really delete it?
            loc_stat = self.stat_path(item['source'], location=location, stats=my_stat)
            if loc_stat:
                res = True
            # Shall we delete if already absent? no!
            test_stat = self.stat_path(item['source'], location=opposite, stats=other_stats)
            if not test_stat:
                res = True
        else:#MOVE
            source_stat = self.stat_path(item['source'], location=opposite, stats=other_stats)
            target_stat = self.stat_path(item['target'], location=opposite, stats=other_stats)
            if not target_stat or source_stat:
                return False
            elif item['node']['md5'] == 'directory':
                res = True
            elif target_stat['size'] == item['node']['bytesize']:# WE SHOULD TEST MD5 HERE AS WELL!
                res = True

        if res:
            if item['type'] != 'delete':
                logging.info('['+location+'] Filtering out ' + item['type'] + ': ' + item['node']['node_path'])
            else:
                logging.info('['+location+'] Filtering out ' + item['type'] + ' ' + item['source'])
            self.remove_seq(item['seq'], location)
            return True

        return False

    def changes_sorter(self, i1, i2):
        # no node: delete on top
        if not i1['node']:
            return -1
        if not i2['node']:
            return 1

        # directory
        if i1['node']['md5'] == 'directory' and i2['node']['md5'] == 'directory':
            return cmp(i1['node']['node_path'], i2['node']['node_path'])

        if i1['node']['md5'] == 'directory':
            return -1
        if i2['node']['md5'] == 'directory':
            return 1

        # sort on path otherwise
        return cmp(i1['node']['node_path'], i2['node']['node_path'])

    def process_change(self, item):

        location = item['location']
        if item['type'] == 'create' or item['type'] == 'content':
            if item['node']['md5'] == 'directory':
                if item['node']['node_path']:
                    logging.info('[' + location + '] Create folder ' + item['node']['node_path'])
                    if location == 'remote':
                        os.makedirs(self.basepath + item['node']['node_path'])
                    else:
                        self.sdk.mkdir(item['node']['node_path'])
            else:
                if item['node']['node_path']:
                    if location == 'remote':
                        logging.info('[' + location + '] Should download ' + item['node']['node_path'])
                        self.sdk.download(item['node']['node_path'], self.basepath + item['node']['node_path'])
                    else:
                        logging.info('[' + location + '] Should upload ' + item['node']['node_path'])
                        self.sdk.upload(self.basepath+item['node']['node_path'], item['node']['node_path'])

        elif item['type'] == 'delete':
            logging.info('[' + location + '] Should delete ' + item['source'])
            if location == 'remote':
                if os.path.isdir(self.basepath + item['source']):
                    self.system.rmdir(item['source'])
                elif os.path.isfile(self.basepath + item['source']):
                    os.unlink(self.basepath + item['source'])
            else:
                self.sdk.delete(item['source'])

        else:
            logging.info('[' + location + '] Should move ' + item['source'] + ' to ' + item['target'])
            if location == 'remote':
                if os.path.exists(self.basepath + item['source']):
                    if not os.path.exists(self.basepath + os.path.dirname(item['target'])):
                        os.makedirs(self.basepath + os.path.dirname(item['target']))
                    os.rename(self.basepath + item['source'], self.basepath + item['target'])
            else:
                self.sdk.rename(item['source'], item['target'])

    def reduce_changes(self, local_changes=dict(), remote_changes=dict()):

        rchanges = remote_changes['data'].values()
        lchanges = local_changes['data'].values()

        for seq, item in local_changes['data'].items():
            pathes = []
            if item['source'] != 'NULL':
                pathes.append(item['source'])
            if item['target'] != 'NULL':
                pathes.append(item['target'])
            # search these pathes in remote_changes
            remote_sequences = []
            for x in pathes:
                remote_sequences = remote_sequences + remote_changes['path_to_seqs'].setdefault(x, [])
            for seq_id in remote_sequences:
                otheritem = remote_changes['data'][seq_id]
                try:
                    if not (item['type'] == otheritem['type']):
                        continue
                    if not item['node'] and not otheritem['node'] and (item['source'] == otheritem['source']):
                        lchanges.remove(item)
                        rchanges.remove(otheritem)
                        self.remove_seq(item['seq'], 'local')
                        self.remove_seq(otheritem['seq'], 'remote')
                        break

                    if not (os.path.normpath(item['node']['node_path']) == os.path.normpath(otheritem['node']['node_path'])):
                        continue
                    if item['node']['bytesize'] == otheritem['node']['bytesize'] and item['node']['md5'] == otheritem['node']['md5']:
                        lchanges.remove(item)
                        rchanges.remove(otheritem)
                        self.remove_seq(item['seq'], 'local')
                        self.remove_seq(otheritem['seq'], 'remote')
                        break
                except Exception as e:
                    pass

        test_stats = list(set(map(lambda it: it['source'] if it['source'] != 'NULL' else it['target'], lchanges)))
        remote_stats = None
        if len(test_stats):
            remote_stats = self.sdk.bulk_stat(test_stats)

        rchanges = filter(lambda it: not self.filter_change(it, remote_stats, None), rchanges)
        lchanges = filter(lambda it: not self.filter_change(it, None, remote_stats), lchanges)

        for item in lchanges:
            rchanges.append(item)

        return sorted(rchanges, cmp=self.changes_sorter)

    def get_remote_changes(self, seq_id, changes=dict()):

        logging.debug('Remote sequence ' + str(seq_id))
        data = self.sdk.changes(seq_id)
        for (i, item) in enumerate(data['changes']):
            item['location'] = 'remote'
            key = item['source'] if item['source'] != 'NULL' else item['target']
            if not key in changes['path_to_seqs']:
                changes['path_to_seqs'][key] = []
            changes['path_to_seqs'][key].append(item['seq'])
            changes['data'][item['seq']] = item

        return data['last_seq']
