#! /usr/bin/env python
# -*- coding: <encoding name> -*-

# Copyright 2017, Abstrium SAS

from unittest import TestCase

from pydio.job.job_config import JobConfig, JobsLoader


JOBS_ROOT_PATH = "/tmp"
SERVER_ADDR = "http://foo.com/path/to/resource?test=true"
WORKSPACE_NAME = "test"
TEST_ID = "foo.com-test"
BLACKLIST = ['.*', '*/.*', '/recycle_bin*', '*.pydio_dl', '*.DS_Store',
             '.~lock.*', '~*', '*.xlk', '*.tmp']
JOB_CONFIG_DICT = {
    'direction': 'bi',
    'filters': {
        'excludes': [
            u'.*',
            u'*/.*',
            u'/recycle_bin*',
            u'*.pydio_dl',
            u'*.DS_Store',
            u'.~lock.*',
            u'~*',
            u'*.xlk',
            u'*.tmp'
        ],

        'includes': [u'*']
    },
    'poolsize': 4,
    'hide_bi_dir': 'false',
    'start_time': {'h': 0, 'm': 0},
    '__type__': 'JobConfig',
    'timeout': 20,
    'server': SERVER_ADDR,
    'trust_ssl': False,
    'remote_folder': '',
    'hide_down_dir': 'false',
    'frequency': 'auto',
    'solve': 'manual',
    'user': '',
    'workspace': WORKSPACE_NAME,
    'hide_up_dir': 'false',
    'directory': '',
    'label': TEST_ID,
    'active': True,
    'id': TEST_ID
}


def init():
    JobsLoader.Instance(data_path=JOBS_ROOT_PATH).jobs = {}


class TestJobConfig(TestCase):

    """Test pydio.job.job_config.JobConfig"""
    def setUp(self):
        self.cfg = JobConfig()
        # test against a non-trivial URL.
        self.cfg.server = SERVER_ADDR
        self.cfg.workspace = WORKSPACE_NAME

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
        self.cfg.make_id()
        self.assertEqual(self.cfg.id, TEST_ID, "malformed base id")

        # test incrementation
        JobsLoader.Instance().jobs[TEST_ID] = None
        self.cfg.make_id()
        self.assertEqual(self.cfg.id, "foo.com-test-1", "improper id incrementation")

    def test_encoder(self):
        self.cfg.make_id()
        # JobConfig.encoder is a static method
        res = JobConfig.encoder(self.cfg)
        self.assertEqual(res, JOB_CONFIG_DICT)
        self.assertRaises(
            TypeError,
            JobConfig.encoder,
            {},
            "non-JobConfig-instances should raise a TypeError"
        )

    def test_object_decoder(self):
        # JobConfig.object_decoder is a static method
        res = JobConfig.object_decoder(JOB_CONFIG_DICT)
        self.assertIsInstance(
            res, JobConfig,
            "known-valid JobConfig dict did not produce a JobConfig instance"
        )

        negtest = {"__type__": "random"}
        self.assertIs(
            JobConfig.object_decoder(negtest), negtest,
            ("Dicts with a '__type__' key that do not match 'JobConfig' should "
             "be returned unchanged")
        )


if __name__ != "__main__":
     init()
