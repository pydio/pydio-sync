#! /usr/bin/env python
# -*- coding: <encoding name> -*-

# Copyright 2017, Abstrium SAS

from unittest import TestCase

from pydio.job.job_config import JobConfig


BLACKLIST = ['.*', '*/.*', '/recycle_bin*', '*.pydio_dl', '*.DS_Store',
             '.~lock.*', '~*', '*.xlk', '*.tmp']


class TestJobConfig(TestCase):
    """Test pydio.job.job_config.JobConfig"""
    def setUp(self):
        self.cfg = JobConfig()

    def test_filters(self):
        self.assertEqual(self.cfg.filters["includes"], ["*"])
        self.assertEqual(self.cfg.filters["excludes"], BLACKLIST)

    def test_init(self):
        kw = dict(
            server='TEST_SERVER',
            directory="TEST_DIRECTORY",
            workspace="TEST_DIRECTORY",
            remote_folder="TEST_REMOTE_FOLDER",
            user_id="TEST_USER_ID",
            label="TEST_LABEL",
            server_configs="TEST_SERVER_CONFIGS",
            active="TEST_ACTIVE",
            direction="TEST_DIRECTION",
            frequency="TEST_FREQUENCY",
            start_time="TEST_START_TIME",
            solve="TEST_SOLVE",
            monitor="TEST_MONITOR",
            trust_ssl="TEST_TRUST_SSL",
            timeout=9001,  # it's over 9000!
            hide_up_dir="TEST_HIDE_UP_DIR",
            hide_bi_dir="TEST_HIDE_BI_DIR",
            hide_down_dir="TEST_HIDE_DOWN_DIR"
        )

        cfg = JobConfig(**kw)

        for k, v in kw.iteritems():
            self.assertEqual(getattr(cfg, k), v)
