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

import time
import os
import threading
import pickle
import logging

from requests.exceptions import ConnectionError
from collections import deque
from pydio.job.change_processor import ChangeProcessor
from pydio.job.localdb import LocalDbHandler
from pydio.job.local_watcher import LocalWatcher
from pydio.sdk.exceptions import ProcessException, InterruptException
from pydio.sdk.remote import PydioSdk
from pydio.sdk.local import SystemSdk
from pydio.job.EventLogger import EventLogger

from pydispatch import dispatcher
from pydio import PUBLISH_SIGNAL, TRANSFER_RATE_SIGNAL, TRANSFER_CALLBACK_SIGNAL
# -*- coding: utf-8 -*-

class ContinuousDiffMerger(threading.Thread):
    """Main Thread grabbing changes from both sides, computing the necessary changes to apply, and applying them"""

    def __init__(self, job_config, job_data_path):
        """
        Initialize thread internals
        :param job_config: JobConfig instance
        :param job_data_path: Filesystem path where the job data are stored
        :return:
        """
        threading.Thread.__init__(self)
        self.data_base = job_data_path
        self.job_config = job_config
        self.init_global_progress()

        self.basepath = job_config.directory
        self.ws_id = job_config.workspace
        self.sdk = PydioSdk(
            job_config.server,
            ws_id=self.ws_id,
            remote_folder=job_config.remote_folder,
            user_id=job_config.user_id
        )
        self.system = SystemSdk(job_config.directory)
        self.remote_seq = 0
        self.local_seq = 0
        self.local_target_seq = 0
        self.remote_target_seq = 0
        self.local_seqs = []
        self.remote_seqs = []
        self.db_handler = LocalDbHandler(self.data_base, job_config.directory)
        self.interrupt = False
        self.event_timer = 2
        self.online_timer = 10
        self.offline_timer = 60
        self.online_status = True
        self.job_status_running = True
        self.direction = job_config.direction
        self.event_logger = EventLogger(self.data_base)
        self.processing_signals = {}
        self.current_tasks = []
        dispatcher.send(signal=PUBLISH_SIGNAL, sender=self, channel='status', message='START')

        if os.path.exists(self.data_base + "/sequences"):
            try:
                sequences = pickle.load(open(self.data_base + "/sequences", "rb"))
                self.remote_seq = sequences['remote']
                self.local_seq = sequences['local']

            except Exception:
                # Wrong content, remove sequences file.
                os.unlink(self.data_base + "/sequences")

        if job_config.direction != 'down':
            self.watcher = LocalWatcher(job_config.directory,
                                        job_config.filters['includes'],
                                        job_config.filters['excludes'],
                                        job_data_path)
        dispatcher.connect( self.handle_transfer_rate_event, signal=TRANSFER_RATE_SIGNAL, sender=dispatcher.Any )
        dispatcher.connect( self.handle_transfer_callback_event, signal=TRANSFER_CALLBACK_SIGNAL, sender=dispatcher.Any )

    def handle_transfer_callback_event(self, sender, change):
        self.processing_signals[change['target']] = change
        self.global_progress["queue_bytesize"] -= change['bytes_sent']
        self.global_progress["queue_done"] += float(change['bytes_sent']) / float(change["total_size"])

    def handle_transfer_rate_event(self, sender, transfer_rate):
        """
        Handler for TRANSFER_SIGNAL to update the transfer rate internally. It's averaged with previous value.
        :param sender:Any
        :param transfer_rate:float
        :return:
        """
        if self.global_progress['last_transfer_rate'] > 0:
            self.global_progress['last_transfer_rate'] = (float(transfer_rate) + self.global_progress['last_transfer_rate']) / 2.0
        else:
            self.global_progress['last_transfer_rate'] = float(transfer_rate)

    def is_running(self):
        """
        Whether the job is in Running state or not.
        :return:bool
        """
        return self.job_status_running

    def init_global_progress(self):
        """
        Initialize the internal progress data
        :return:None
        """
        self.global_progress = {
            'queue_length'      :0,
            'queue_done'        :0.0,
            'queue_bytesize'    :0,
            'last_transfer_rate':-1,
            'queue_start_time'  :time.clock(),
            'total_time'        :0
        }

    def update_global_progress(self):
        """
        Compute a dict representation with many indications about the current state of the queue
        :return: dict
        """
        self.global_progress['total_time'] = time.clock() - self.global_progress['queue_start_time']
        self.global_progress["queue_bytesize"] = self.compute_queue_bytesize()
        # compute an eta
        eta = -1
        if self.global_progress['last_transfer_rate'] > -1 and self.global_progress['queue_bytesize'] > 0 :
            eta = self.global_progress['queue_bytesize'] / self.global_progress['last_transfer_rate']
        elif self.global_progress['queue_done']:
            remaining_operations = self.global_progress['queue_length'] - self.global_progress['queue_done']
            eta = remaining_operations * self.global_progress['total_time'] / self.global_progress['queue_done']

        self.global_progress['eta'] = eta

        #logging.info(self.global_progress)
        return self.global_progress

    def get_global_progress(self):
        return self.global_progress

    def update_current_tasks(self, cursor=0, limit=5):
        """
        Get a list of the current tasks
        :return: list()
        """
        if not hasattr(self, 'current_store'):
            return []
        self.current_tasks = self.current_store.list_changes(cursor, limit)
        for change in self.current_tasks:
            if change['target'] in self.processing_signals:
                progress = self.processing_signals[change['target']]
                for key in progress.keys():
                    change[key] = progress[key]

    def get_current_tasks(self):
        return {
            'total': self.global_progress['queue_length'],
            'current': self.current_tasks
        }

    def compute_queue_bytesize(self):
        """
        Sum all the bytesize of the nodes that are planned to be uploaded/downloaded in the queue.
        :return:float
        """
        if not hasattr(self, 'current_store'):
            return 0
        total = 0
        exclude_pathes = []
        for task in self.processing_signals:
            if 'remaining_bytes' in task:
                total += float(task['remaining_bytes'])
                exclude_pathes.append('"' + task['target'] + '"')
        where = ''
        if len(exclude_pathes):
            where = "target IN (" + ','.join(exclude_pathes) + ")"
            return self.current_store.sum_sizes(where)
        else:
            return self.current_store.sum_sizes()

    def start_now(self):
        """
        Resume task (set it in running mode) and make sure the cycle starts now
        :return:
        """
        self.last_run = 0
        self.resume()

    def pause(self):
        """
        Set the task in pause. The thread is still running, but the cycle does nothing.
        :return:None
        """
        self.job_status_running = False
        self.info('Job Paused', toUser='PAUSE', channel='status')

    def resume(self):
        """
        Set the task out of pause mode.
        :return:
        """
        self.job_status_running = True
        self.info('Job Started', toUser='START', channel='status')

    def stop(self):
        """
        Set the thread in "interrupt" mode : will try to stop cleanly, and then the thread will stop.
        :return:
        """
        if hasattr(self, 'watcher'):
            logging.debug("Stopping watcher: %s" % self.watcher)
            self.watcher.stop()
        self.info('Job stopping', toUser='PAUSE', channel='status')
        self.interrupt = True

    def sleep_offline(self):
        """
        Sleep the thread for a "long" time (offline time)
        :return:
        """
        self.online_status = False
        self.last_run = time.time()
        time.sleep(self.event_timer)

    def sleep_online(self):
        """
        Sleep the thread for a "short" time (online time)
        :return:
        """
        self.online_status = True
        self.last_run = time.time()
        time.sleep(self.event_timer)

    def run(self):
        """
        Start the thread
        """
        if hasattr(self, 'watcher'):
            self.watcher.start()

        self.last_run = 0
        logger = EventLogger(self.data_base)

        while not self.interrupt:

            try:
                # logging.info('Starting cycle with cycles local %i and remote %is' % (self.local_seq, self.remote_seq))
                self.processing_signals = {}
                self.init_global_progress()
                interval = int(time.time() - self.last_run)
                if (self.online_status and interval < self.online_timer) or (not self.online_status and interval < self.offline_timer):
                    time.sleep(self.event_timer)
                    continue

                if not self.job_status_running:
                    logging.debug("self.online_timer: %s" % self.online_timer)
                    self.sleep_offline()
                    continue

                if not self.system.check_basepath():
                    log = 'Cannot find local folder! Did you disconnect a volume? Waiting %s seconds before retry' % self.offline_timer
                    logging.error(log)
                    logger.log_state('Cannot find local folder! Did you disconnect a volume?', "error")
                    self.sleep_offline()
                    continue

                # Load local and/or remote changes, depending on the direction
                from pydio.job.change_stores import SqliteChangeStore
                self.current_store = SqliteChangeStore(self.data_base + '/changes.sqlite', self.job_config.filters['includes'], self.job_config.filters['excludes'])
                self.current_store.open()
                try:
                    if self.job_config.direction != 'up':
                        logging.info('Loading remote changes with sequence ' + str(self.remote_seq))
                        if self.remote_seq == 0:
                            logger.log_state('Computing data that will be loaded from workspace, this can take a while for the first time', 'sync')
                        self.remote_target_seq = self.load_remote_changes_in_store(self.remote_seq, self.current_store)
                        self.current_store.sync()
                    else:
                        self.remote_target_seq = 1
                        self.ping_remote()
                except ConnectionError as ce:
                    error = 'No connection detected, waiting %s seconds to retry' % self.offline_timer
                    logging.error(error)
                    logger.log_state(error, "wait")
                    self.sleep_offline()
                    continue
                except Exception as e:
                    error = 'Error while connecting to remote server (%s), waiting for %i seconds before retempting ' % (e.message, self.offline_timer)
                    logging.error(error)
                    logger.log_state('Error while connecting to remote server (%s)' % e.message, "error")
                    self.sleep_offline()
                    continue
                self.online_status = True
                if not self.job_config.server_configs:
                    self.job_config.server_configs = self.sdk.load_server_configs()
                self.sdk.set_server_configs(self.job_config.server_configs)

                if self.job_config.direction != 'down':
                    logging.info('Loading local changes with sequence ' + str(self.local_seq))
                    local_changes = dict(data=dict(), path_to_seqs=dict())
                    self.local_target_seq = self.db_handler.get_local_changes(self.local_seq, local_changes)
                    self.current_store.massive_store("local", local_changes)
                    self.current_store.sync()
                else:
                    self.local_target_seq = 1

                logging.info('Reducing changes')

                self.current_store.dedup_changes()
                self.update_min_seqs_from_store()
                self.current_store.detect_unnecessary_changes(local_sdk=self.system, remote_sdk=self.sdk)
                self.update_min_seqs_from_store()
                self.current_store.filter_out_echoes_events()
                self.update_min_seqs_from_store()
                self.current_store.clear_operations_buffer()
                self.current_store.prune_folders_moves()
                self.update_min_seqs_from_store()

                store_conflicts = self.current_store.clean_and_detect_conflicts(self.db_handler)
                if store_conflicts:
                    logging.info('Conflicts detected, cannot continue!')
                    logger.log_state('Conflicts detected, cannot continue!', 'error')
                    self.current_store.close()
                    self.sleep_offline()
                    continue

                changes_length = len(self.current_store)
                if changes_length:
                    import change_processor
                    self.global_progress['queue_length'] = changes_length
                    logging.info('Processing %i changes' % changes_length)
                    logger.log_state('Processing %i changes' % changes_length, "start")
                    counter = [1]
                    def processor_callback(change):
                        try:
                            if self.interrupt or not self.job_status_running:
                                raise InterruptException()
                            self.update_current_tasks()
                            self.update_global_progress()
                            proc = ChangeProcessor(change, self.current_store, self.job_config, self.system, self.sdk,
                                                   self.db_handler, self.event_logger)
                            proc.process_change()
                            self.update_min_seqs_from_store(success=True)
                            self.global_progress['queue_done'] = float(counter[0])
                            counter[0] += 1
                            self.update_current_tasks()
                            self.update_global_progress()
                            time.sleep(0.1)
                            if self.interrupt or not self.job_status_running:
                                raise InterruptException()
                        except ProcessException as pe:
                            logging.error(pe.message)
                        except InterruptException as i:
                            raise i
                        except Exception as e:
                            logging.error(e.message)

                    try:
                        self.current_store.process_changes_with_callback(processor_callback)
                    except InterruptException as iexc:
                        pass
                    logger.log_state('%i files modified' % self.global_progress['queue_done'], "success")
                else:
                    logging.info('No changes detected')

            except Exception as e:
                logging.error('Unexpected Error: %s' % e.message)
                logger.log_state('Unexpected Error: %s' % e.message, 'error')

            logging.info('Finished this cycle, waiting for %i seconds' % self.online_timer)
            self.current_store.close()
            self.init_global_progress()
            self.sleep_online()

    def update_min_seqs_from_store(self, success=False):
        self.local_seq = self.current_store.get_min_seq('local', success=success)
        if self.local_seq == -1:
            self.local_seq = self.local_target_seq
        self.remote_seq = self.current_store.get_min_seq('remote', success=success)
        if self.remote_seq == -1:
            self.remote_seq = self.remote_target_seq
        logging.debug('Storing sequences remote %i local %i', self.local_seq, self.remote_seq)
        pickle.dump(dict(
            local=self.local_seq,
            remote=self.remote_seq
        ), open(self.data_base + '/sequences', 'wb'))

    def ping_remote(self):
        """
        Simple stat of the remote server root, to know if it's reachable.
        :return:bool
        """
        test = self.sdk.stat('/')
        return (test != False)

    def info(self, message, toUser=False, channel='sync'):
        logging.info(message)
        if toUser:
            dispatcher.send(signal=PUBLISH_SIGNAL, sender=self, channel=channel, message=message)

    def load_remote_changes_in_store(self, seq_id, store):
        last_seq = self.sdk.changes_stream(seq_id, store.store)
        return last_seq
