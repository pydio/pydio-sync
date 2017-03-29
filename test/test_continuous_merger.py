#! /usr/bin/env python
# -*- coding: <encoding name> -*-

# Copyright 2017, Abstrium SAS

from unittest import TestCase

import os.path as osp

from pydio.job.continous_merger import ContinuousDiffMerger
from pydio.utils.global_config import ConfigManager, GlobalConfigManager
from pydio.job.job_config import JobConfig

from fixtures.sdklocal import SystemSdkStub


SQLITE_PATH = ":memory:"
WORKSPACE_PATH = "/workspace"
TMP_PATH = "/tmp"


def init():
    # configs path is the appdata path
    # data path is something like ~/Pydio (equiv. to the dropbox folder ?)
    gcm =  GlobalConfigManager.Instance(configs_path=TMP_PATH)
    gcm.configs_path = TMP_PATH
    gcm.set_general_config(gcm.default_settings)
    ConfigManager.Instance(configs_path=TMP_PATH, data_path="")


class TestContinuousDiffMerger(TestCase):
    def setUp(self):
        job_config = JobConfig()
        job_config.online_timer = 10
        self.cdm = ContinuousDiffMerger(job_config, WORKSPACE_PATH)

    def test_update_sequence_file(self):
        import pickle
        self.cdm.update_sequences_file("LOCALSEQ", "REMOTESEQ")
        with open(osp.join(WORKSPACE_PATH, "sequences")) as f:
            seq = pickle.loads(f.read())
        self.assertEqual(seq, dict(local="LOCALSEQ", remote="REMOTESEQ"))

    def test_handle_transfer_callback_event(self):
        total_size = 10240
        bytes_sent = 1024  # pretend we always send a kilobyte
        total_bytes_sent = 0
        target = "some_file"

        for _ in range(10):
            total_bytes_sent += 1024
            change = dict(
                target=target,
                bytes_sent=bytes_sent,
                total_size=total_size,
                total_bytes_sent=total_bytes_sent
            )

            self.cdm.handle_transfer_callback_event(None, change)  # arg1 unused
            self.assertEqual(
                self.cdm.processing_signals[change["target"]], change
            )
            self.assertEqual(
                self.cdm.global_progress["queue_bytesize"],
                total_size - total_bytes_sent
            )

        # When everything is said and done, we should have 100% of the file.
        self.assertAlmostEqual(self.cdm.global_progress["queue_done"], 1.0)

    def test_is_running(self):
        self.assertIsInstance(self.cdm.is_running(), bool)

    def test_init_global_progress(self):
        self.cdm.init_global_progress()
        keys = (
            'status_indexing',
            'queue_length',
            'queue_done',
            'queue_bytesize',
            'total_time'
        )
        for k in keys:
            self.assertFalse(self.cdm.global_progress[k])

        self.assertIsInstance(self.cdm.global_progress["queue_start_time"], float)
        self.assertEqual(self.cdm.global_progress["last_transfer_rate"], -1)

    def test_start_now(self):
        self.cdm.last_run = 9001
        self.cdm.sdk.interrupt_tasks = True
        self.cdm.start_now()
        self.assertFalse(self.cdm.last_run,
                         "ContinuousDiffMerger.last_run not set to 0")
        self.assertFalse(self.cdm.sdk.interrupt_tasks, "interrupt still set")

    def test_pause(self):
        self.cdm.job_status_running = True
        self.cdm.sdk.interrupt_tasks = False
        self.cdm.pause()
        self.assertFalse(self.cdm.job_status_running, "job still running")
        self.assertTrue(self.cdm.sdk.interrupt_tasks, "interrupt not set")

    def test_resume(self):
        self.cdm.pause()
        self.cdm.resume()
        self.assertTrue(self.cdm.job_status_running, "job still suspended")
        self.assertFalse(self.cdm.sdk.interrupt_tasks, "interrupt still set")

    def test_stop(self):
        self.cdm.resume()
        self.cdm.stop()
        self.assertTrue(self.cdm.watcher.interrupt, "interrupt not set")
        self.assertTrue(self.cdm.watcher.is_alive, "watcher was killed")



if __name__ != "__main__":
    init()
