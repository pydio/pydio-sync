#  -*- coding: utf-8 -*-
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

import time
import datetime
import os
import sys
import threading
import pickle
import logging
from functools import partial
from pydispatch import dispatcher
from requests.exceptions import RequestException, Timeout, SSLError, ProxyError, TooManyRedirects, ChunkedEncodingError, ContentDecodingError, InvalidSchema, InvalidURL
try:
    from pydio.job.change_processor import ChangeProcessor, StorageChangeProcessor
    from pydio.job.job_config import JobsLoader
    from pydio.job.localdb import LocalDbHandler, SqlEventHandler, DBCorruptedException
    from pydio.job.local_watcher import LocalWatcher
    from pydio.job.change_stores import SqliteChangeStore
    from pydio.job.EventLogger import EventLogger
    from pydio.sdkremote.pydio_exceptions import ProcessException, InterruptException, PydioSdkDefaultException, PydioSdkException
    from pydio.sdkremote.remote import PydioSdk
    from pydio.sdklocal.local import SystemSdk
    from pydio.utils.functions import connection_helper
    from pydio.utils.global_config import ConfigManager
    from pydio.utils.pydio_profiler import pydio_profile
    from pydio.utils.check_sqlite import check_sqlite_file
    from pydio import PUBLISH_SIGNAL, TRANSFER_RATE_SIGNAL, TRANSFER_CALLBACK_SIGNAL
    from pydio.utils import i18n
    _ = i18n.language.ugettext
except ImportError:
    from job.change_processor import ChangeProcessor, StorageChangeProcessor
    from job.job_config import JobsLoader
    from job.localdb import LocalDbHandler, SqlEventHandler, DBCorruptedException
    from job.change_stores import SqliteChangeStore
    from job.EventLogger import EventLogger
    from job.local_watcher import LocalWatcher
    from sdkremote.pydio_exceptions import ProcessException, InterruptException, PydioSdkDefaultException, PydioSdkException
    from sdkremote.remote import PydioSdk
    from sdklocal.local import SystemSdk
    from utils.functions import connection_helper
    from utils.global_config import ConfigManager
    from utils.pydio_profiler import pydio_profile
    from utils.check_sqlite import check_sqlite_file
    from utils import i18n
    _ = i18n.language.ugettext
    COMMAND_SIGNAL = 'command'
    JOB_COMMAND_SIGNAL = 'job_command'
    PUBLISH_SIGNAL = 'publish'
    TRANSFER_RATE_SIGNAL = 'transfer_rate'
    TRANSFER_CALLBACK_SIGNAL = 'transfer_callback'


class SigContinue(Exception):
    """Raised when a sync run cannot continue, but the ContinuousDiffMerger
    instance is in a consistent state.
    """


class Ctr(object):
    def __init__(self, i=0):
        self.i = i


class ContinuousDiffMerger(threading.Thread):
    """Main Thread grabbing changes from both sides, computing the necessary changes to apply, and applying them"""

    _sync_deadline = datetime.timedelta(minutes=1)

    @pydio_profile
    def __init__(self, job_config, job_data_path):
        """
        Initialize thread internals
        :param job_config: JobConfig instance
        :param job_data_path: Filesystem path where the job data are stored
        :return:
        """
        super(ContinuousDiffMerger, self).__init__()
        self.last_run = 0
        self.very_first = False
        self.configs_path = job_data_path
        self.job_config = job_config
        sqlite_files = [file for file in os.listdir(self.configs_path) if file.endswith(".sqlite")]

        for sqlite_file in sqlite_files:
            try:
                exists_and_correct = check_sqlite_file(os.path.join(self.configs_path, sqlite_file))
                if exists_and_correct:
                    logging.info("Structure and Integrity of SQLite file %s is intact " % str(
                        os.path.join(self.configs_path, sqlite_file)))
            except DBCorruptedException as e:
                logging.debug("SQLite file %s is corrupted (Reason: %s), Deleting file and Reinitialising sync"
                              % (str(os.path.join(self.configs_path, sqlite_file)), e.message))
                os.unlink(os.path.join(self.configs_path, sqlite_file))
                self.update_sequences_file(0, 0)

        self.init_global_progress()

        self.basepath = job_config.directory
        self.ws_id = job_config.workspace
        self.sdk = PydioSdk(
            job_config.server,
            ws_id=self.ws_id,
            remote_folder=job_config.remote_folder,
            user_id=job_config.user_id,
            device_id=ConfigManager.Instance().device_id,
            skip_ssl_verify=job_config.trust_ssl,
            proxies=ConfigManager.Instance().defined_proxies,
            timeout=job_config.timeout
        )
        self.system = SystemSdk(job_config.directory)
        self.remote_seq = 0
        self.local_seq = 0
        self.local_target_seq = 0
        self.remote_target_seq = 0
        self.local_seqs = []
        self.remote_seqs = []
        self.db_handler = LocalDbHandler(self.configs_path, job_config.directory)
        self.interrupt = False
        self.event_timer = 2
        self.online_timer = job_config.online_timer
        self.offline_timer = 60
        self.online_status = True
        self.job_status_running = True
        self.direction = job_config.direction
        self.event_logger = EventLogger(self.configs_path)
        self.processing_signals = {}
        self.current_tasks = []
        self.event_handler = None
        self.watcher = None
        self.watcher_first_run = True
        # TODO: TO BE LOADED FROM CONFIG
        self.storage_watcher = job_config.label.startswith('LSYNC')
        self.wait_for_changes = False  # True when no changes detected in last cycle, can be used to disable websockets
        self.marked_for_snapshot_pathes = []
        self.processing = False  # indicates whether changes are being processed

        dispatcher.send(signal=PUBLISH_SIGNAL, sender=self, channel='status', message='START')
        if job_config.direction != 'down' or (self.job_config.direction == 'down' and self.job_config.solve != 'remote'):
            self.event_handler = SqlEventHandler(includes=job_config.filters['includes'],
                                                 excludes=job_config.filters['excludes'],
                                                 basepath=job_config.directory,
                                                 job_data_path=self.configs_path)
            self.watcher = LocalWatcher(job_config.directory,
                                        self.configs_path,
                                        event_handler=self.event_handler)
            self.db_handler.check_lock_on_event_handler(self.event_handler)

        if os.path.exists(os.path.join(self.configs_path, "sequences")):
            try:
                with open(os.path.join(self.configs_path, "sequences"), "rb") as f:
                    sequences = pickle.load(f)
                self.remote_seq = sequences['remote']
                self.local_seq = sequences['local']
                if self.event_handler:
                    self.event_handler.last_seq_id = self.local_seq

            except Exception as e:
                logging.exception(e)
                # Wrong content, remove sequences file.
                os.unlink(os.path.join(self.configs_path, "sequences"))

        dispatcher.connect(self.handle_transfer_rate_event, signal=TRANSFER_RATE_SIGNAL, sender=self.sdk)
        dispatcher.connect(self.handle_transfer_callback_event, signal=TRANSFER_CALLBACK_SIGNAL, sender=self.sdk)

        if self.job_config.frequency == 'manual':
            self.job_status_running = False
        self.logger = EventLogger(self.configs_path)
    # end init

    def update_sequences_file(self, local_seq, remote_seq):
        with open(os.path.join(self.configs_path, "sequences"), "wb") as f:
            pickle.dump(dict(
                local=local_seq,
                remote=remote_seq
            ), f)

    @pydio_profile
    def handle_transfer_callback_event(self, sender, change):
        self.processing_signals[change['target']] = change
        self.global_progress["queue_bytesize"] -= change['bytes_sent']
        # The following 3 lines are a dirty fix, only working for one file at a time size relaining... Better than NaN
        if self.global_progress["queue_bytesize"] < 0:
            self.global_progress["queue_bytesize"] = abs(self.global_progress["queue_bytesize"])
            self.global_progress["queue_bytesize"] = max(change['total_size'] - change['total_bytes_sent'], self.global_progress["queue_bytesize"])
        self.global_progress["queue_done"] += float(change['bytes_sent']) / float(change["total_size"])

    @pydio_profile
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

    @pydio_profile
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
            'status_indexing'   :0,
            'queue_length'      :0,
            'queue_done'        :0.0,
            'queue_bytesize'    :0,
            'last_transfer_rate':-1,
            'queue_start_time'  :time.clock(),
            'total_time'        :0
        }

    @pydio_profile
    def update_global_progress(self, compute_queue_size=True):
        """
        Compute a dict representation with many indications about the current state of the queue
        :return: dict
        """
        self.global_progress['total_time'] = time.clock() - self.global_progress['queue_start_time']
        if compute_queue_size:
            self.global_progress["queue_bytesize"] = self.compute_queue_bytesize()
        # compute an eta
        eta = -1
        if self.global_progress['last_transfer_rate'] > -1 and self.global_progress['queue_bytesize'] > 0:
            eta = self.global_progress['queue_bytesize'] / self.global_progress['last_transfer_rate']
        elif self.global_progress['queue_done']:
            remaining_operations = self.global_progress['queue_length'] - self.global_progress['queue_done']
            eta = remaining_operations * self.global_progress['total_time'] / self.global_progress['queue_done']

        self.global_progress['eta'] = eta

        #logging.info(self.global_progress)
        return self.global_progress

    def get_global_progress(self):
        self.update_global_progress(compute_queue_size=False)
        return self.global_progress

    @pydio_profile
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

    @pydio_profile
    def get_current_tasks(self):
        for change in self.current_tasks:
            if change['target'] in self.processing_signals:
                progress = self.processing_signals[change['target']]
                for key in progress.keys():
                    change[key] = progress[key]
        return {
            'total': self.global_progress['queue_length'],
            'current': self.current_tasks
        }

    def get_websocket_status(self):
        return self.sdk.waiter and self.sdk.waiter.ws.connected

    @pydio_profile
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
        if len(exclude_pathes):
            where = "target IN (" + ','.join(exclude_pathes) + ")"
            return self.current_store.sum_sizes(where)
        else:
            return self.current_store.sum_sizes()

    @pydio_profile
    def start_now(self):
        """
        Resume task (set it in running mode) and make sure the cycle starts now
        :return:
        """
        self.last_run = 0
        self.sdk.remove_interrupt()
        self.resume()

    def pause(self):
        """
        Set the task in pause. The thread is still running, but the cycle does nothing.
        :return:None
        """
        self.job_status_running = False
        self.sdk.set_interrupt()
        self.info(_('Job Paused'), toUser='PAUSE', channel='status')

    @pydio_profile
    def resume(self):
        """
        Set the task out of pause mode.
        :return:
        """
        self.job_status_running = True
        self.sdk.proxies = ConfigManager.Instance().defined_proxies
        self.sdk.remove_interrupt()
        self.info(_('Job Started'), toUser='START', channel='status')

    def stop(self):
        """
        Set the thread in "interrupt" mode : will try to stop cleanly, and then the thread will stop.
        :return:
        """
        if self.watcher:
            logging.debug("Stopping watcher: %s" % self.watcher)
            self.watcher.stop()
        self.info(_('Job stopping'), toUser='PAUSE', channel='status')
        self.sdk.set_interrupt()
        self.interrupt = True

    def sleep(self, online=True):
        """Put the thread to sleep.

        :online: if True, signals that the thread is sleeping briefly, else signals
                 a long-term pause.
        """
        self.online_status = online
        self.last_run = time.time()
        time.sleep(self.event_timer)

    def exit_loop_clean(self, logger):
        #self.marked_for_snapshot_pathes = []
        self.current_store.close()
        self.init_global_progress()
        logger.log_state(_('Synchronized'), 'success')
        if self.job_config.frequency == 'manual':
            self.job_status_running = False
            self.sleep(online=False)
        else:
            self.sleep()

    @property
    def sync_interval_elapsed(self):
        """If True, the requisite interval between sync runs has elapsed and the
        application should proceed with the next run.
        """
        interval = time.time() - self.last_run
        if self.online_status:
            return interval > self.online_timer
        else:
            return interval > self.offline_timer

    @property
    def scheduled_start_time(self):
        """The time at which a scheduled sync job should start.
        N.B.:  this does -not- concern automatic and manual sync runs.

        returns None or datetime object
        """
        if self.job_config.frequency != "time":
            return None
        return datetime.time(
            int(self.job_config.start_time['h']),
            int(self.job_config.start_time['m']),
        )

    def _check_ready_for_sync_run(self):
        """Check if it's time to run a sync pass, AND there are no concurrent
        passes presently engaged.

        :return:bool
        """
        # When sync mode is automatic, we will, depending on the
        # ContinuousDiffMerger's state (ONLINE || OFFLINE), wait some
        # variable amount of time before engaging in the next sync run.
        if not self.sync_interval_elapsed:
            self.sleep(online=True)
            raise SigContinue("_check_ready_for_sync_run: interval not elapsed")

        # don't run if a job is already running
        if not self.job_status_running:
            logging.debug("self.online_timer: %s" % self.online_timer)
            self.logger.log_state(_('Status: Paused'), "sync")
            self.sleep(online=False)
            raise SigContinue("_check_ready_for_sync_run: job already running")

        # When the sync is scheduled for a specific time, prevent sync
        # run until such time is reached.
        if self.scheduled_start_time is not None:
            now = datetime.datetime.now().time()
            end_time = now + self._sync_deadline
            if not (self.scheduled_start_time < now < end_time):
                self.logger.log_state(_('Status: scheduled for {0}'.format(self.scheduled_start_time)), "sync")
                self.sleep(online=False)
                raise SigContinue("_check_ready_for_sync_run: scheduled time not reached")
            else:
                logging.info("Now triggering synchro as expected at time {0}".format(self.scheduled_start_time))

    def _init_sync_run(self):
        self.processing_signals.clear()
        self.init_global_progress()
        if self.very_first:
            self.global_progress["status_indexing"] = 1

    def _check_local_volume(self):
        """make sure the local volume still exists"""
        if not self.system.check_basepath():
            log = _('Cannot find local folder! Did you disconnect a volume? Waiting %s seconds before retry') % self.offline_timer
            logging.error(log)
            self.logger.log_state(_('Cannot find local folder, did you disconnect a volume?'), "error")
            self.sleep(online=False)
            raise SigContinue("_check_local_volume: local folder not found")

    def _check_remote_volume(self):
        """make sure the remote volume still exists"""
        # check that remote folder still exists
        if not self.sdk.check_basepath():
            # if it doesn't, try to create it
            self.sdk.remote_folder = os.path.join("/", self.sdk.remote_folder)
            try:
                logging.info("Creating remote directory.")
                self.sdk.mkdir("")
            except Exception as e:  # TODO: restrict to expected exceptions
                logging.exception(e)
                self.sleep(online=False)
            if not self.sdk.check_basepath():
                log = _('Cannot find remote folder, maybe it was renamed? Sync cannot start, please check the configuration.')
                logging.error(log)
                self.logger.log_state(log, 'error')
                self.sleep(online=False)
                raise SigContinue("_check_remote_volume: could not find remote folder")

    def _check_target_volumes(self):
        """Verify that local and remote sync targets are present and accessible.
        """
        self._check_local_volume()
        self._check_remote_volume()


    def _load_directory_snapshots(self):
        """Check for changes in workspace directories since last sync pass.

        raises : InterruptException
        """
        if self.watcher is not None:
            for snap_path in self.marked_for_snapshot_pathes:
                logging.info('LOCAL SNAPSHOT : loading snapshot for directory %s' % snap_path)
                if self.interrupt or not self.job_status_running:
                    raise InterruptException

                self.watcher.check_from_snapshot(snap_path)

            self.marked_for_snapshot_pathes = []

    def _wait_db_lock(self):
        """To avoid reading events before they're written (db lock) wait for writing to finish"""
        writewait = .5
        while self.event_handler is not None and self.event_handler.locked:
            logging.info("Waiting for changes to be written before retrieving remote changes.")
            if writewait < 5:
                writewait += .5
            time.sleep(writewait)

    def _fetch_remote_changes(self):
        if self.job_config.direction != 'up':
            logging.info(
                'Loading remote changes with sequence {0:s} for job id {1:s}'.format(str(self.remote_seq),
                                                                                       str(self.job_config.id)))
            if self.remote_seq == 0:
                self.logger.log_state(_('Gathering data from remote workspace, this can take a while...'), 'sync')
                self.very_first = True
            self.remote_target_seq = self.load_remote_changes_in_store(self.remote_seq, self.current_store)
            self.current_store.sync()
        else:
            self.remote_target_seq = 1
            self.ping_remote()

    def _fetch_local_changes(self):
        down = self.job_config.direction == "down"
        local = self.job_config.solve != 'remote'
        if not down or (down and local):
            msg = 'Loading local changes with sequence {0} for job id {1}'.format(
                self.local_seq,
                self.job_config.id
            )
            logging.info(msg)

            self.local_target_seq = self.db_handler.get_local_changes_as_stream(
                self.local_seq,
                self.current_store.flatten_and_store
            )

            self.current_store.sync()
        else:
            self.local_target_seq = 1

        if not connection_helper.internet_ok:
            connection_helper.is_connected_to_internet(self.sdk.proxies)

    def _abort_sync_run(self):
        self.processing = False
        self.update_min_seqs_from_store()
        self.wait_for_changes = True
        self.exit_loop_clean(self.logger)

    def _watcher_diagnostics(self):
        if not self.watcher.isAlive() and not self.interrupt:
            logging.info("File watcher died, restarting...")
            self.watcher.stop()
            self.watcher = LocalWatcher(self.job_config.directory,
                                        self.configs_path,
                                        event_handler=self.event_handler)
            self.start_watcher()

    def _preprocess_changes(self):
        logging.debug('[CMERGER] Delete Copies ' + self.job_config.id)
        self.current_store.delete_copies()
        self.update_min_seqs_from_store()
        logging.debug('[CMERGER] Dedup changes ' + self.job_config.id)
        self.current_store.dedup_changes()
        self.update_min_seqs_from_store()
        if not self.storage_watcher or self.very_first:
            logging.debug('[CMERGER] Detect unnecessary changes ' + self.ws_id)
            self.logger.log_state(_('Detecting unecessary changes...'), 'sync')
            self.current_store.detect_unnecessary_changes()
            logging.debug('[CMERGER] Done detecting unnecessary changes')
            self.logger.log_state(_('Done detecting unecessary changes...'), 'sync')
        self.update_min_seqs_from_store()
        logging.debug('Clearing op and pruning folders moves ' + self.job_config.id)
        self.current_store.clear_operations_buffer()
        self.current_store.prune_folders_moves()
        self.update_min_seqs_from_store()

        logging.debug('Store conflicts ' + self.job_config.id)
        return self.current_store.clean_and_detect_conflicts(self.db_handler)

    def _resolve_conflicts(self, conflicts):
        if conflicts:
            if self.job_config.solve == 'both':
                logging.info('Marking nodes SOLVED:KEEPBOTH')
                for row in self.db_handler.list_conflict_nodes():
                    self.db_handler.update_node_status(row['node_path'], 'SOLVED:KEEPBOTH')
                conflicts = self.current_store.clean_and_detect_conflicts(self.db_handler)
            if self.job_config.solve == 'local':
                logging.info('Marking nodes SOLVED:KEEPLOCAL')
                for row in self.db_handler.list_conflict_nodes():
                    self.db_handler.update_node_status(row['node_path'], 'SOLVED:KEEPLOCAL')
                conflicts = self.current_store.clean_and_detect_conflicts(self.db_handler)
            if self.job_config.solve == 'remote':
                logging.info('Marking nodes SOLVED:KEEPREMOTE')
                for row in self.db_handler.list_conflict_nodes():
                    self.db_handler.update_node_status(row['node_path'], 'SOLVED:KEEPREMOTE')
                conflicts = self.current_store.clean_and_detect_conflicts(self.db_handler)
            return conflicts

    def _update_marked_for_snapshot_paths(self):
        mod_par_set = set(self.current_store.find_modified_parents())
        snapsh_set = set(self.marked_for_snapshot_pathes)
        self.marked_for_snapshot_pathes = list(mod_par_set - snapsh_set)

    def _do_sync(self, changes_length):
        self.global_progress['status_indexing'] = 0
        self.global_progress['queue_length'] = changes_length

        logging.info('Processing %i changes' % changes_length)
        self.logger.log_state(_('Processing %i changes') % changes_length, "start")

        counter = Ctr(1)

        try:
            if sys.platform.startswith('win'):
                self._update_marked_for_snapshot_paths()

            if not self.processing:
                self.processing = True
                for i in self.current_store.process_changes_with_callback(partial(self.processor_callback, counter), self.processor_callback2, self):
                    if self.interrupt:
                        raise InterruptException
                    #logging.info("Updating seqs")
                    self.current_store.process_pending_changes()
                    self.update_min_seqs_from_store(success=True)
                    self.global_progress['queue_done'] = float(counter.i)
                    counter.i += 1
                    self.update_current_tasks()
                    self.update_global_progress()
                    time.sleep(0.05)  # Allow for changes to be noticeable in UI
                time.sleep(.5)
                self.current_store.process_pending_changes()
                self.update_min_seqs_from_store(success=True)
                self.update_current_tasks()
                self.update_global_progress()
                #logging.info("DONE WITH CHANGES")
                self.processing = False

        except InterruptException:
            msg = "ContinuousDiffMerger._do_sync :: caught InterruptException"
            logging.debug(msg)

    def _compute_changes(self):
        # REMOTE CHANGES
        try:
            self._fetch_remote_changes()
        except RequestException as ce:
            logging.exception(ce)
            if not connection_helper.is_connected_to_internet(self.sdk.proxies):
                error = _('No Internet connection detected! Waiting for %s seconds to retry') % self.offline_timer
            else:
                error = _('Connection to server failed, server is probably down. Waiting %s seconds to retry') % self.offline_timer
            self.marked_for_snapshot_pathes = []
            logging.error(error)
            self.logger.log_state(error, "wait")
            self.sleep(online=False)
            raise SigContinue("_compute_changes: request exception")
        except Exception as e:
            error = 'Error while connecting to remote server (%s), waiting for %i seconds before retempting ' % (e.message, self.offline_timer)
            logging.exception(e)
            self.logger.log_state(_('Error while connecting to remote server (%s)') % e.message, "error")
            self.marked_for_snapshot_pathes = []
            self.sleep(online=False)
            raise SigContinue("_compute_changes: generic exception")

        self.online_status = True
        if not self.job_config.server_configs:
            self.job_config.server_configs = self.sdk.load_server_configs()
        self.sdk.set_server_configs(self.job_config.server_configs)

        # LOCAL CHANGES
        self._fetch_local_changes()

    def _merge(self):
        # EVALUATE CHANGES
        if not len(self.current_store):
            logging.info(
                'No changes detected in {0}'.format(self.job_config.id)
            )

            self.very_first = False
            self._abort_sync_run()
            self._watcher_diagnostics()

            raise SigContinue("_merge: no changes to commit")

        # START MERGE LOGIC
        logging.info('Reducing changes for ' + self.job_config.id)
        self.logger.log_state(_(
            'Merging changes between remote and local, please wait...'
        ), 'sync')

        self.global_progress['status_indexing'] = 1
        # We are updating the status to IDLE here for the nodes which has status as NEW
        # The reason is when we create a new sync on the existing folder, some of the files might
        # already be synchronized and we ignore those files while we Dedup changes and those files
        # remain untouched later.
        # So the flow of node status change will occur as follows
        # NEW (as soon as we create a new sync task)
        #  |
        # IDLE (here, just before we reduce changes)
        #  |
        # PENDING (those files/folders which remain after reducing changes and to be actually processed)
        #  |
        # UP / DOWN / CONFLICT (corresponding the operation which occurs)
        #  |
        # IDLE (The final state once upload/ download happens or once when the conflict is resolved)
        self.db_handler.update_bulk_node_status_as_idle()

        if self._resolve_conflicts(self._preprocess_changes()):
            logging.info('Conflicts detected, cannot continue!')
            self.logger.log_state(_('Conflicts detected, cannot continue!'), 'error')
            self.current_store.close()
            self.sleep(online=False)
            self.logger.log_notif(_('Conflicts detected, cannot continue!'), 'error')
            raise SigContinue("_merge: conflicts detected. cannot continue.")

        if self.job_config.direction == 'down' and self.job_config.solve != 'remote':
            self.current_store.remove_based_on_location('local')
            self.update_min_seqs_from_store()

        changes_length = len(self.current_store)
        if not changes_length:
            logging.info('No changes detected for ' + self.job_config.id)
            self.exit_loop_clean(self.logger)
            self.very_first = False
            raise SigContinue("_merge: no changes detected for {0}".format(self.job_config.id))

        self.current_store.update_pending_status(self.db_handler, self.local_seq)
        self._do_sync(changes_length)

    @pydio_profile
    def run(self):
        """
        Start the thread
        """
        self.start_watcher()

        while not self.interrupt:
            self._init_sync_run()

            try:
                self._check_ready_for_sync_run()
                self._check_target_volumes()

                self._load_directory_snapshots()

                self._wait_db_lock()

                # TODO : don't open a new SQL connection on each iteration.
                # Load local and/or remote changes, depending on the direction
                self.current_store = SqliteChangeStore(
                    self.configs_path + '/changes.sqlite',
                    self.job_config.filters['includes'],
                    self.job_config.filters['excludes'],
                    self.job_config.poolsize,
                    local_sdk=self.system,
                    remote_sdk=self.sdk,
                    job_config=self.job_config,
                    db_handler=self.db_handler,
                )
                self.current_store.open()

                self._compute_changes()

                self._merge()

                # Log success & sleep
                self.logger.log_state(
                    _('%i files modified') % self.global_progress['queue_done'],
                    'success'
                )

                if self.global_progress['queue_done']:
                    self.logger.log_notif(
                        _('%i files modified') % self.global_progress['queue_done'],
                        'success'
                    )
                self.exit_loop_clean(self.logger)

            except SigContinue as sigcont:
                continue
            #
            # TODO:  catch these exceptions closer to their source to avoid the
            #        present clusterfuck.
            #
            except PydioSdkDefaultException as re:
                logging.error(re.message)
                self.logger.log_state(re.message, 'error')
            except SSLError as rt:
                logging.error(rt.message)
                self.logger.log_state(_('An SSL error happened, please check the logs'), 'error')
            except ProxyError as rt:
                logging.error(rt.message)
                self.logger.log_state(_('A proxy error happened, please check the logs'), 'error')
            except TooManyRedirects as rt:
                logging.error(rt.message)
                self.logger.log_state(_('Connection error: too many redirects'), 'error')
            except ChunkedEncodingError as rt:
                logging.error(rt.message)
                self.logger.log_state(_('Chunked encoding error, please check the logs'), 'error')
            except ContentDecodingError as rt:
                logging.error(rt.message)
                self.logger.log_state(_('Content Decoding error, please check the logs'), 'error')
            except InvalidSchema as rt:
                logging.error(rt.message)
                self.logger.log_state(_('Http connection error: invalid schema.'), 'error')
            except InvalidURL as rt:
                logging.error(rt.message)
                self.logger.log_state(_('Http connection error: invalid URL.'), 'error')
            except Timeout as to:
                logging.error(to)
                self.logger.log_state(_('Connection timeout, will retry later.'), 'error')
            except RequestException as ree:
                logging.error(ree.message)
                self.logger.log_state(_('Cannot resolve domain!'), 'error')
                self.sleep(online=False)
            except Exception as e:
                if not (e.message.lower().count('[quota limit reached]') or e.message.lower().count('[file permissions]')):
                    logging.exception('Unexpected Error: %s' % e.message)
                    self.logger.log_state(_('Unexpected Error: %s') % e.message, 'error')
                else:
                    logging.exception(e)
                self.sleep(online=False)

            logging.debug('Finished this cycle, waiting for %i seconds' % self.online_timer)
            self.very_first = False

    def processor_callback(self, counter, change):
        """
        :counter:Ctr
        """
        try:
            if self.interrupt or not self.job_status_running:
                raise InterruptException()
            self.update_current_tasks()
            self.update_global_progress()
            Processor = StorageChangeProcessor if self.storage_watcher else ChangeProcessor
            proc = Processor(change, self.current_store, self.job_config, self.system, self.sdk,
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
            return False
        except InterruptException as i:
            raise i
        except PydioSdkDefaultException as p:
            raise p
        except Exception as ex:
            logging.exception(ex)
            return False
        return True


    def processor_callback2(self, change):
        try:
            if self.interrupt or not self.job_status_running:
                raise InterruptException()
            Processor = StorageChangeProcessor if self.storage_watcher else ChangeProcessor
            proc = Processor(change, self.current_store, self.job_config, self.system, self.sdk,
                                   self.db_handler, self.event_logger)
            proc.process_change()
            if self.interrupt or not self.job_status_running:
                raise InterruptException()
        except PydioSdkException as pe:
            if pe.message.find("Original file") > -1:
                pe.code = 1404
                raise pe
        except ProcessException as pe:
            logging.error(pe.message)
            return False
        except PydioSdkDefaultException as p:
            raise p
        except InterruptException as i:
            raise i
        return True

    def start_watcher(self):
        if self.watcher:
            if self.watcher_first_run:
                def status_callback(status):
                    self.logger.log_state(status, 'sync')
                self.init_global_progress()

                try:
                    self.global_progress['status_indexing'] = 1
                    self.logger.log_state(_('Checking changes since last launch...'), "sync")
                    self.very_first = True
                    self.db_handler.update_bulk_node_status_as_idle()
                    self.watcher.check_from_snapshot(state_callback=status_callback)
                except DBCorruptedException as e:
                    self.stop()
                    JobsLoader.Instance().clear_job_data(self.job_config.id)
                    logging.error(e)
                    return
                except Exception as e:
                    logging.exception(e)
                    self.interrupt = True
                    self.logger.log_state(_('Oops, error while indexing the local folder. Pausing the task.'), 'error')
                    logging.error(e)

                self.watcher_first_run = False
            self.watcher.start()

    @pydio_profile
    def update_min_seqs_from_store(self, success=False):
        self.local_seq = self.current_store.get_min_seq('local', success=success)
        if self.local_seq == -1:
            self.local_seq = self.local_target_seq
        self.remote_seq = self.current_store.get_min_seq('remote', success=success)
        if self.remote_seq == -1:
            self.remote_seq = self.remote_target_seq
        #logging.info('Storing sequences remote=%i local=%i', self.remote_seq, self.local_seq)
        self.update_sequences_file(self.local_seq, self.remote_seq)
        if self.event_handler:
            self.event_handler.last_seq_id = self.local_seq

    @pydio_profile
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

    @pydio_profile
    def load_remote_changes_in_store(self, seq_id, store):
        last_seq = self.sdk.changes_stream(seq_id, store.flatten_and_store)
        if self.wait_for_changes:
            timereq = time.time()
            try:
                if self.sdk.waiter is None:
                    self.sdk.websocket_connect(last_seq, str(self.job_config.id))
                if self.sdk.waiter and self.sdk.waiter.ws.connected:
                    self.sdk.waiter.should_fetch_changes = False
                    while not self.sdk.waiter.should_fetch_changes and not self.interrupt:
                        time.sleep(2)
                        # these break only after one run
                        if self.local_seq != self.db_handler.get_max_seq():
                            # There was a local change
                            break
                        if not self.sdk.waiter.ws.connected:
                            # websocket disconnected
                            break
            except Exception as e:
                logging.exception(e)
            if time.time() - timereq > 10:  # if last_seq was updated more than 10s ago, update it
                last_seq = self.sdk.changes_stream(seq_id, store.flatten_and_store)
        return last_seq
