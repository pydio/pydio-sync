# coding=utf-8
#
# Copyright 2010 Ergore sp. z o.o.
# All rights reserved.
#
# This source code and all resulting intermediate files are CONFIDENTIAL and
# PROPRIETY TRADE SECRETS of Brave Labs sp. z o.o.
# Use is subject to license terms. See NOTICE file of this project for details.


# install current version of distribute setuptools
# http://pythonhosted.org/distribute/setuptools.html#using-setuptools-without-bundling-it

import os, platform
from setuptools import setup, find_packages

if platform.platform().startswith('Linux'):
    req_lines = [line.strip() for line in open('requirements.txt').readlines()]
    install_reqs = list(filter(None, req_lines))
else:
    from pip.req import parse_requirements
    install_requires = parse_requirements(os.path.join(os.path.dirname(__file__), "requirements.txt"))
    install_reqs = [str(r.req) for r in install_requires]

setup_kwargs = {
    'name': "pydio",
    'version': "0.1",
    'packages': find_packages("src"),
    # 'scripts':  ['py/pydio.py'],
    'package_dir': {'': 'src'},
    'install_requires': install_reqs,

    "package_data": {
        'pydio': ['res/*.sql']
    },

    # metadata for upload to PyPI
    'author': "Charles du Jeu",
    'author_email': "contact@pyd.io",
    'description': "Python version of the Pydio synchronization client [experimental].",
    'license': "todo",
    'keywords': "todo",
    'url': "http://pyd.io/",

    # Create an entry programs for this package
    "entry_points": {
        'console_scripts': [
            'pydio = pydio.main:main',
        ],
    },
}

setup(**setup_kwargs)

