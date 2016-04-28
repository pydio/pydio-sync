# -*- coding: utf-8 -*-
# Copyright 2007-2016 Charles du Jeu - Abstrium SAS <team (at) pydio.com>
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
#  The latest code can be found at <http://pydio.com/>.
#

import fnmatch
from watchdog.utils.dirsnapshot import DirectorySnapshot as dirsnap
from requests.exceptions import ReadTimeout
import logging
import platform
import unicodedata
import os
import time

def toset(prefix, pathset):
    """ transform an absolute path set to a relative path set """
    rel_path = set()
    for p in pathset:
        rel_path.add(p.replace(prefix, ''))
    return rel_path

def docheck(sdk, path, subfolder=""):
    """ Using PydioSdk connects to a server and compares the list of files at
        :param path: with the list of files at the :param sdk:
    """
    try:
        remote_ls = sdk.list(recursive='true')
    except ReadTimeout:
        logging.info("Recursive list failed")
    if subfolder != "":
        remote2 = {}
        for p in remote_ls:
            remote2[p.replace(subfolder, "", 1)] = remote_ls[p]
        remote_ls = remote2
    local_ls = dirsnap(path)
    def dodiff(remotefiles, localfiles):
        """ from {'path/to/file': file, ...}, set('path/to/file', ...) do a
            check that the same files are present returns dict of dict of files
            {missing_local, missing_remote}
        """
        missing = {}
        for k in remotefiles.keys():
            try:
                if platform.system() == 'Darwin':
                    localfiles.remove(unicodedata.normalize('NFD', k))
                else:
                    localfiles.remove(os.path.normpath(k))
            except KeyError as e:
                missing[k] = time.time()
        return {"missing_local" : missing, "missing_remote": localfiles}
    #print(remote_ls)
    diff = dodiff(remote_ls, toset(path, local_ls.paths))
    return diff

def parseWithExcludes(diff, excludes):
    """ Parses a diff, returns only items not matching excludes
        :param diff: will be MUTATED
        :param excludes: the list of patterns to delete
        TODO This code could probably be heavily optimized if the need appeared
    """
    ndiff = {"missing_remote": dict(), "missing_local": dict()}
    excludes.append('')
    for p in diff["missing_local"].keys():
        skip = False
        for patt in excludes:
            if fnmatch.fnmatch(p, patt):
                skip = True
                break
        if not skip:
            ndiff["missing_local"][p] = diff["missing_local"][p]
    for p in diff["missing_remote"]:
        skip = False
        for patt in excludes:
            if fnmatch.fnmatch(p, patt):
                skip = True
                break
        if not skip:
            ndiff["missing_remote"][p] = ""
    return ndiff

def dofullcheck(jobid, conf, sdk):
    """
    Ask the remote sdk for a recursive list of files, compares with the local tree
    :param jobid: the job_id to check
    :param conf: the information from job_configs.json
    :param sdk: a remote sdk
    :return: dictionary containing path to missing files (missing_remote, missing_local)
    """
    excludes = conf[jobid].filters['excludes']
    diff = docheck(sdk, conf[jobid].directory, conf[jobid].remote_folder)
    cleaned = parseWithExcludes(diff, excludes)
    return cleaned

