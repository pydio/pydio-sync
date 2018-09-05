import json
import os
import unittest


def flatten(location, row, last_info=None):
    first = None
    second = None

    if last_info is None:
        last_info = dict()
    previous_id = last_info['node_id'] if (last_info and last_info.has_key('node_id')) else -1
    change = last_info['change'] if (last_info and last_info.has_key('change')) else dict()
    max_seq = last_info['max_seq'] if (last_info and last_info.has_key('max_seq')) else -1
    type_seq = last_info['type_seq'] if (last_info and last_info.has_key('type_seq')) else {}

    if not row:
        if last_info and last_info.has_key('change') and change:
            first, second = reformat(location, change, type_seq)
    else:
        seq = row.pop('seq')
        max_seq = seq if seq > max_seq else max_seq
        last_info['max_seq'] = max_seq

        source = row.pop('source')
        target = row.pop('target')
        if source == 'NULL':
            source = os.path.sep
        if target == 'NULL':
            target = os.path.sep
        change_type = row.pop('type')

        if previous_id != row['node_id']:
            if previous_id != -1:
                try:
                    first, second = reformat(location, change, type_seq)
                except:
                    print "error"

            last_info['type_seq'] = [change_type]
            last_info['change'] = None
            last_info['node_id'] = row['node_id']
            change = dict()
        else:
            type_seq.append(change_type)

        if not change:
            change['source'] = source
            change['dp'] = PathOperation.path_sub(target, source)
            change['dc'] = (change_type == 'content')
            change['seq'] = seq
            change['node'] = row
        else:
            dp = PathOperation.path_sub(target, source)
            change['dp'] = PathOperation.path_add(change['dp'], dp)
            change['dc'] = ((change_type == 'content') or change['dc'])
            change['seq'] = seq

        last_info['change'] = change
        last_info['max_seq'] = max_seq
    return first, second


def reformat(location, change, type_seq):
    source = change.pop('source')
    dp = change.pop('dp')
    target = PathOperation.path_add(source, dp)
    if not target.startswith(os.sep):
        target = os.sep + target

    if source == os.path.sep:
        source = u"NULL"
    if target == os.path.sep:
        target = u"NULL"

    seq = change.pop('seq')
    node_id = change['node'].pop('node_id')
    stat_result = change['node'].pop('stat_result') if change['node'].has_key('stat_result') else None
    node = change.pop("node")
    if node.has_key("node"):
        node = node["node"]

    flatten_change_type = ""

    for t in type_seq:
        if t == "delete":
            flatten_change_type = t

        elif t == "create":
            flatten_change_type = "create"

        elif t == "content":
            if flatten_change_type == "create" or flatten_change_type == "delete":
                flatten_change_type = "create"

            elif flatten_change_type == "path":
                flatten_change_type = "edit_move"

            else:
                flatten_change_type = t

        elif t == "path":
            if flatten_change_type == "create" or flatten_change_type == "delete":
                flatten_change_type = "create" if source == u"NULL" else "path"

            elif flatten_change_type == "content":
                flatten_change_type = "edit_move"

            else:
                flatten_change_type = t
        else:
            flatten_change_type = t

    if flatten_change_type == "delete":
        if source == u"NULL":
            return None, None
        first = {'location': location, 'node_id': node_id, 'source': source, 'target': 'NULL', 'type': 'delete',
                 'seq': seq, 'stat_result': stat_result, 'node': node}
        return first, None

    if flatten_change_type == "create":
        if target == u"NULL":
            return None, None

        first = {'location': location, 'node_id': node_id, 'source': source, 'target': target, 'type': 'create',
                 'seq': seq, 'stat_result': stat_result, 'node': node}
        return first, None

    if flatten_change_type == "content":
        first = {'location': location, 'node_id': node_id, 'source': source, 'target': source, 'type': 'content',
                 'seq': seq, 'stat_result': stat_result, 'node': node}
        return first, None

    if flatten_change_type == "path":
        first = {'location': location, 'node_id': node_id, 'source': source, 'target': target, 'type': 'path',
                 'seq': seq, 'stat_result': stat_result, 'node': node}
        return first, None

    else:
        first = {'location': location, 'node_id': node_id, 'source': source, 'target': target, 'type': 'path',
                 'seq': seq, 'stat_result': stat_result, 'node': node}

        second = {'location': location, 'node_id': node_id, 'source': source, 'target': source, 'type': 'content',
                 'seq': seq, 'stat_result': stat_result, 'node': node}

        return first, second


class PathOperation(object):
    @staticmethod
    def path_add(path, delta):
        return os.path.normpath(os.path.join(path, delta))

    @staticmethod
    def path_sub(path, path2):
        return os.path.relpath(path, path2)

    @staticmethod
    def path_compare(path1, path2):
        return os.path.normcase(os.path.normpath(path1)) == os.path.normcase(os.path.normpath(path2))


class TestStringMethods(unittest.TestCase):

    def test_flatten(self):
        changes = [
            """{
                "seq": 5071,
                "node_id": 542,
                "type": "content",
                "source": "/Excel_files_test.xlsx",
                "target": "/Excel_files_test.xlsx",
                "node": {
                    "bytesize": 9664,
                    "md5": "880f91bf1ef85498d479f745285edf38",
                    "mtime": 1530792621,
                    "node_path": "/recycle_bin/Excel_files_test.xlsx",
                    "repository_identifier": "1-admin"
                }
            }""",
            """{
                "seq": 5072,
                "node_id": 542,
                "type": "delete",
                "source": "/Excel_files_test.xlsx",
                "target": "NULL",
                "node": {
                    "bytesize": 9664,
                    "md5": "880f91bf1ef85498d479f745285edf38",
                    "mtime": 1530792621,
                    "node_path": "/recycle_bin/Excel_files_test.xlsx",
                    "repository_identifier": "1-admin"
                }
            }""",
            """{
                 "seq": 5358,
                 "node_id": 542,
                 "type": "create",
                 "source": "NULL",
                 "target": "/Excel_files_test.xlsx",
                 "node": {
                     "bytesize": 9664,
                     "md5": "880f91bf1ef85498d479f745285edf38",
                     "mtime": 1530792621,
                     "node_path": "/recycle_bin/Excel_files_test.xlsx",
                     "repository_identifier": "1-admin"
                 }
            }""",
            """{
                "seq": 5360,
                "node_id": 542,
                "type": "content",
                "source": "/Excel_files_test.xlsx",
                "target": "/Excel_files_test.xlsx",
                    "node": {
                       "bytesize": 9664,
                       "md5": "880f91bf1ef85498d479f745285edf38",
                       "mtime": 1530792621,
                       "node_path": "/recycle_bin/Excel_files_test.xlsx",
                       "repository_identifier": "1-admin"
                    }
                }""",
            """{
                "seq": 5362,
                "node_id": 542,
                "type": "content",
                "source": "/Excel_files_test.xlsx",
                "target": "/Excel_files_test.xlsx",
                "node": {
                    "bytesize": 9664,
                    "md5": "880f91bf1ef85498d479f745285edf38",
                    "mtime": 1530792621,
                    "node_path": "/recycle_bin/Excel_files_test.xlsx",
                    "repository_identifier": "1-admin"
                }
            }""",
            """{
                "seq": 5364,
                "node_id": 542,
                "type": "delete",
                "source": "/Excel_files_test.xlsx",
                "target": "NULL",
                "node": {
                    "bytesize": 9664,
                    "md5": "880f91bf1ef85498d479f745285edf38",
                    "mtime": 1530792621,
                    "node_path": "/recycle_bin/Excel_files_test.xlsx",
                    "repository_identifier": "1-admin"
                }
            }"""
        ]

        location = "test"
        last_info = {}
        for s in changes:
            c = json.loads(s, strict=False)
            flatten(location, c, last_info)

        first, second = flatten(location, None, last_info)
        self.assertNotEqual(first, None)
        if first:
            source = first["source"]
            target = first["target"]

            self.assertEqual(source, u"/Excel_files_test.xlsx", "Flattened change source must be NULL")
            self.assertEqual(target, u"NULL", "Flattened change target must be NULL")

        changes = [
            """{
                "seq": 5071,
                "node_id": 542,
                "type": "create",
                "source": "NULL",
                "target": "/Excel_files_test.xlsx",
                "node": {
                    "bytesize": 9664,
                    "md5": "880f91bf1ef85498d479f745285edf38",
                    "mtime": 1530792621,
                    "node_path": "/recycle_bin/Excel_files_test.xlsx",
                    "repository_identifier": "1-admin"
                }
            }""",
            """{
                "seq": 5072,
                "node_id": 542,
                "type": "path",
                "source": "/Excel_files_test.xlsx",
                "target": "/rupt/Excel_files_test.xlsx",
                "node": {
                    "bytesize": 9664,
                    "md5": "880f91bf1ef85498d479f745285edf38",
                    "mtime": 1530792621,
                    "node_path": "/recycle_bin/Excel_files_test.xlsx",
                    "repository_identifier": "1-admin"
                }
            }"""
        ]
        location = "test"
        last_info = {}
        for s in changes:
            c = json.loads(s, strict=False)
            flatten(location, c, last_info)

        first, second = flatten(location, None, last_info)
        self.assertNotEqual(first, None)
        if first:
            source = first["source"]
            target = first["target"].replace("\\", "/")
            change_type = first["type"]

            self.assertEqual(change_type, u"create", "Flattened change source must be NULL")
            self.assertEqual(source, u"NULL", "Flattened change source must be NULL")
            self.assertEqual(target, u"/rupt/Excel_files_test.xlsx", "Flattened change target must be NULL")

