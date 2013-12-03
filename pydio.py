__author__ = 'charles'
import logging
import sys

from continous_merger import ContinuousDiffMerger
from local_watcher import LocalWatcher

if __name__ == "__main__":

    logging.basicConfig(level=logging.ERROR,
                        format='%(asctime)s - %(message)s',
                        datefmt='%Y-%m-%d %H:%M:%S')
    path = sys.argv[1] if len(sys.argv) > 1 else '/Users/charles/Documents/tmp'

    watcher = LocalWatcher(path)
    merger = ContinuousDiffMerger(local_path=path, remote_ws='files-editable', sdk_url='http://localhost', sdk_auth=('admin','123456'))

    try:
        watcher.start()
        merger.start()
    except (KeyboardInterrupt, SystemExit):
        merger.stop()
        watcher.stop()
        sys.exit()