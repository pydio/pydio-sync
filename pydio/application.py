#! /usr/bin/env python

import os
import os.path as osp

import time
import json
import thread
import logging
import appdirs

from job import manager
from job.job_config import JobConfig, JobsLoader
from job.scheduler import PydioScheduler

from utils.config_ports import PortsDetector
from utils.global_config import ConfigManager
from utils.functions import get_user_home, guess_filesystemencoding

from ui.web_api import PydioApi

APP_NAME = "Pydio"
APP_DATA = dict(
    DEFAULT_DATA_PATH=appdirs.user_data_dir(APP_NAME, roaming=True),
    DEFAULT_PARENT_PATH=get_user_home(APP_NAME),
    DEFAULT_PORT=5556,
    DEFAULT_JOBS_ROOT = osp.join(osp.dirname(__file__), "data"),
)


def init_jobs(appname, appdata, kw):
    path = kw.pop("jobs_root", appdata["DEFAULT_JOBS_ROOT"])
    default_path = appdata["DEFAULT_DATA_PATH"]
    jobs_root = configure_jobs_root(appname, path, default_path)
    return jobs_root, JobsLoader(data_path=jobs_root)


def configure_jobs_root(app_name, job_root, fallback):
    if not osp.isdir(job_root):
        job_root = fallback.encode(guess_filesystemencoding())
        if not osp.isdir(job_root):
            logging.getLogger(__name__).debug("configuring first run")

            user_dir = get_user_home(app_name)
            os.makedirs(job_root)
            if not osp.exists(user_dir):
                os.makedirs(user_dir)
            else:
                from utils.favorites_manager import add_to_favorites
                add_to_favorites(user_dir, app_name)

    return job_root


def configure_ports(jobs_root, kw):
    ports_detector = PortsDetector(
        store_file=osp.join(jobs_root, "ports_config"),
        username=kw.pop("--api-user"),
        password=kw.pop("--api-passwd"),
        default_port=int(kw.pop("--api-port")),
    )
    ports_detector.create_config_file()
    return ports_detector


class Application(object):
    """Pydio-Sync application class"""
    log = logging.getLogger('.'.join((__name__, "Application")))

    def __init__(self, jobs_root, jobs_loader, cfg, **kw):
        self.cfg = cfg  # job_id : JobConfig // e.g.:  {u'sandbox.pydio.com-my-files': <pydio.job.job_config.JobConfig object at 0x10f5ebd10>}
        self._jobs_root = jobs_root
        self.config_manager = ConfigManager(
            configs_path=self.jobs_root,  # use property to get decoded path
            data_path=APP_DATA["DEFAULT_PARENT_PATH"]
        )
        self.jobs_loader = jobs_loader
        if kw.get("--rdiff"):
            self.config_manager.rdiff_path = kw.pop("--rdiff")

        self.log_release_info()

        self._scheduler = PydioScheduler(
            jobs_root_path=self.jobs_root,
            jobs_loader=self.jobs_loader,
        )

        ports_detector = configure_ports(jobs_root, kw)
        self._svr = PydioApi(
            ports_detector.get_port(),
            ports_detector.get_username(),
            ports_detector.get_password(),
            external_ip=kw.pop("--api-addr"),
        )
        manager.api_server = self._svr

    @classmethod
    def from_cli_args(cls, **kw):
        jobs_root, jobs_load = init_jobs(APP_NAME, APP_DATA, kw)

        job_config = JobConfig()
        job_config.from_cli_args(kw)
        cfg = {job_config["id"]: job_config}
        if kw.pop("--save-cfg"):
            cls.log.info("Storing config in {0}".format(
                osp.join(jobs_root, 'configs.json')
            ))
            jobs_load.save_jobs(cfg)

        return cls(jobs_root, jobs_load, cfg, **kw)

    @classmethod
    def from_cfg_file(cls, **kw):
        jobs_root, jobs_load = init_jobs(APP_NAME, APP_DATA, kw)

        # TODO:  this method should raise an exception if a suitable config
        #        file is not found.  At present, it implicitly loads a default
        #        from *somewhere*.
        fp = kw.pop("--file")
        if fp and fp != '.':
            cls.log.info("Loading config from {0}".format(fp))
            jobs_load.config_file = fp
            jobs_load.load_config()

        cfg = jobs_load.get_jobs()
        return cls(jobs_root, jobs_load, cfg, **kw)

    @property
    def jobs_root(self):
        return self._jobs_root.decode(guess_filesystemencoding())

    def run(self):
        thread.start_new_thread(self._svr.start_server, ())
        time.sleep(0.3)
        if not self._svr.running:
            raise RuntimeError("Cannot start web server, exiting application")
        self._scheduler.start_all()

    def halt(self):
        self._svr.shutdown_server()

    def log_release_info(self):
        vdat = self.config_manager.version_info
        self.log.info("Version Number {0:s}".format(vdat["version"]))
        self.log.info("Release Date {0:s}".format(vdat["date"]))

    def configure_proxy(self, prx_args):
        prx_args = prx_args.split("::")
        n_prx_args = len(prx_args)
        if (n_prx_args % 5) not in (0, 1):
            self.log.error("Wrong number of parameters pased for proxy")
            return

        prx_cfg = {}
        for i in range(n_prx_args / 5):
            prx_cfg[prx_args[i * 5]] = {
                "username": prx_args[i * 5 + 1],
                "password": prx_args[i * 5 + 2],
                "hostname": prx_args[i * 5 + 3],
                "port": prx_args[i * 5 + 4]
            }

        self.config_manager.save_proxy_config(prx_cfg)

    def log_config_data(self):
        self.log.debug("data: {0}".format(json.dumps(
            self.cfg,
            default=JobConfig.encoder,
            indent=2,
        )))
