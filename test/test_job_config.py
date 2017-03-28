#! /usr/bin/env python
# -*- coding: <encoding name> -*-

# Copyright 2017, Abstrium SAS

from unittest import TestCase

from pydio.job.job_config import JobConfig, JobsLoader


BLACKLIST = ['.*', '*/.*', '/recycle_bin*', '*.pydio_dl', '*.DS_Store',
             '.~lock.*', '~*', '*.xlk', '*.tmp']
JOBS_ROOT_PATH = "/tmp"


def init():
    JobsLoader.Instance(data_path=JOBS_ROOT_PATH).jobs = {}


class TestJobConfig(TestCase):
    _server_addr = "http://foo.com/path/to/resource?test=true"
    _workspace = "test"

    """Test pydio.job.job_config.JobConfig"""
    def setUp(self):
        self.cfg = JobConfig()
        # test against a non-trivial URL.
        self.cfg.server = self._server_addr
        self.cfg.workspace = self._workspace

    def tearDown(self):
        JobsLoader.Instance().jobs.clear()

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
            hide_down_dir="TEST_HIDE_DOWN_DIR",
            poolsize="TEST_POOL_SIZE",
        )

        cfg = JobConfig(**kw)

        for k, v in kw.iteritems():
            self.assertEqual(getattr(cfg, k), v)

    def test_make_id(self):
        test_id = "foo.com-test"

        self.cfg.make_id()
        self.assertEqual(self.cfg.id, test_id, "malformed base id")

        # test incrementation
        JobsLoader.Instance().jobs[test_id] = None
        self.cfg.make_id()
        self.assertEqual(self.cfg.id, "foo.com-test-1", "improper id incrementation")

    def test_encoder(self):
        self.cfg.make_id()

        # JobConfig.encoder is a static method
        res = JobConfig.encoder(self.cfg)
        # TODO validate res

        self.assertRaises(
            TypeError,
            JobConfig.encoder,
            {},
            "non-JobConfig-instances should raise a TypeError"
        )

if __name__ != "__main__":
     init()
