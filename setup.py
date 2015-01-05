#
# Copyright 2007-2014 Charles du Jeu - Abstrium SAS <team (at) pyd.io>
# This file is part of Pydio.
#
#  Pydio is free software: you can redistribute it and/or modify
#  it under the terms of the GNU Affero General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#
#  Pydio is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU Affero General Public License for more details.
#
#  You should have received a copy of the GNU Affero General Public License
#  along with Pydio.  If not, see <http://www.gnu.org/licenses/>.
#
#  The latest code can be found at <http://pyd.io/>.
#

# install current version of distribute setuptools
# http://pythonhosted.org/distribute/setuptools.html#using-setuptools-without-bundling-it

import os, platform, uuid
from setuptools import setup, find_packages

if platform.platform().startswith('Linux'):
    req_lines = [line.strip() for line in open('requirements.txt').readlines()]
    install_reqs = list(filter(None, req_lines))
else:
    from pip.req import parse_requirements
    install_requires = parse_requirements(os.path.join(os.path.dirname(__file__), "requirements.txt"), None, None,
                                          None, uuid.uuid1())
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

