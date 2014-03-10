__author__ = 'charles'
import logging
import sys
import os
import argparse
import keyring
import slugify

from continous_merger import ContinuousDiffMerger
from local_watcher import LocalWatcher

if __name__ == "__main__":

    logging.basicConfig(level=logging.DEBUG,
                        format='%(asctime)s - %(message)s',
                        datefmt='%Y-%m-%d %H:%M:%S')
    logging.getLogger("requests").setLevel(logging.WARNING)

    parser = argparse.ArgumentParser('Pydio Synchronization Tool')
    parser.add_argument('-s', '--server', help='Server URL, with http(s) and path to pydio', type=unicode, default='http://localhost')
    parser.add_argument('-d', '--directory', help='Local directory', type=unicode, default=None)
    parser.add_argument('-w', '--workspace', help='Id or Alias of workspace to synchronize', type=unicode, default=None)
    parser.add_argument('-u', '--user', help='User name', type=unicode, default=None)
    parser.add_argument('-p', '--password', help='Password', type=unicode, default=None)
    args, _ = parser.parse_known_args()

    if args.password:
        keyring.set_password(args.server, args.user, args.password)

    path = args.directory
    logging.info("Starting on " + args.directory)
    if not os.path.exists(path):
        logging.error("Cannot find path " + path)
        exit()

    job_data_path = 'data/' + slugify.slugify(args.server) + '-' + slugify.slugify(args.workspace)
    if not os.path.exists(job_data_path):
        os.mkdir(job_data_path)

    watcher = LocalWatcher(path, includes=['*'], excludes=['.*','recycle_bin'], data_path=job_data_path)
    merger = ContinuousDiffMerger(local_path=path, remote_ws=args.workspace, sdk_url=args.server,
                                  job_data_path=job_data_path, sdk_user_id=args.user)

    try:
        watcher.start()
        merger.start()
    except (KeyboardInterrupt, SystemExit):
        merger.stop()
        watcher.stop()
        sys.exit()