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

import os
from setuptools import setup, find_packages
from pip.req import parse_requirements

install_requires = parse_requirements(os.path.join(os.path.dirname(__file__), "requirements.txt"))

setup_kwargs = {
    'name': "pydio",
    'version': "0.1",
    'packages': find_packages("src"),
    # 'scripts':  ['py/pydio.py'],
    'package_dir': {'': 'src'},
    'install_requires': [str(r.req) for r in install_requires],

    # 'package_data': {457
    #     # If any package contains *.txt or *.rst files, include them:
    #     '': ['*.txt', '*.rst'],
    #     # And include any *.msg files found in the 'hello' package, too:
    #     'hello': ['*.msg'],
    # },

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

