#! /usr/bin/env python
# -*- coding: <encoding name> -*-

# Copyright 2017, Abstrium SAS


class SystemSdkStub(object):
    """SystemSdkStub provides stubs for the local Pydio SDK such that test_stats
    can be effectuated without relying on network IO.
    """

    def check_basepath(self):
        """
        Check if basepath exists or not
        :return: bool
        """
        return True

    def bulk_stat(self, paths, with_hash=False):
        return None

    def mkfile(self, path):
        raise NotImplementedError

    def stat(self, path, full_path=False, with_hash=False):
        """
        Format filesystem stat in the same way as it's returned by server for remote stats.
        :param path:local path (starting from basepath)
        :param full_path:optionaly pass full path
        :param with_hash:add file content hash in the result
        :return:dict() an fstat lile result:
        {
            'size':1231
            'mtime':1214365
            'mode':0255
            'inode':3255
            'hash':'1F3R4234RZEdgFGD'
        }
        """
        raise NotImplementedError

    def rmdir(self, path):
        """
        Delete a folder recursively on filesystem
        :param path:Path of the folder to remove, starting from basepath
        :return:bool True
        """
        raise NotImplementedError

    def rsync_signature(self, file_path, signature_path):
        raise NotImplementedError

    def rsync_delta(self, file_path, signature_path, delta_path):
        raise NotImplementedError

    def duplicateWith(self, file_path, custom="mine"):
        """
        Copies the file from file_path, keeps the extension and optionally add a custom path modifier to the filename
        :param file_path: file that will be duplicated
        :param custom: custom path modifier used to identify the copied file
        """
        raise NotImplementedError

    def isinternetavailable(self):
        """
        :return: True when an interface is configured ~= computer is online
        """
        raise NotImplementedError
