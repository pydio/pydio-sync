# coding=utf-8
# Created 2014 by Janusz Skonieczny
import os

hiddenimports = [
    'zmq.backend.cffi',
    'zmq.backend.cython',
]

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

datas = [
    (os.path.join(ROOT, 'src', 'pydio', 'res', "*"), 'res'),
]
