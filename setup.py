#
# Copyright 2007-2014 Charles du Jeu - Abstrium SAS <team (at) pyd.io>
# This file is part of Pydio.
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
#  The latest code can be found at <http://pyd.io/>.
#

# install current version of distribute setuptools
# http://pythonhosted.org/distribute/setuptools.html#using-setuptools-without-bundling-it

import os
from uuid import uuid1
from platform import platform
from pip.req import parse_requirements

from setuptools import setup

def get_deps():
    if platform().startswith('Linux'):
        with open('requirements.txt') as f:
            return filter(None, map(str.strip, f.readlines()))

    abspath = os.path.join(os.path.dirname(__file__), "requirements.txt")
    install_requires = parse_requirements(
        abspath,
        None,
        None,
        None,
        uuid1()
    )
    return [str(r.req) for r in install_requires]

setup(
    name="pydio",
    version="0.1",
    author="Louis Thibault",
    author_email="contact@pyd.io",
    description="Pydio synchronization client.",

    packages=["pydio"],
    install_requires=get_deps(),
    package_data= {'pydio': ['res/*.sql',
                             'ui/app/*.html',
                             'ui/app/*.js',
                             'ui/app/assets/*.js',
                             'ui/app/assets/*.css',
                             'ui/app/assets/images/*.png',
                             'ui/app/src/jobs/view/*.html',
                             'ui/app/src/jobs/*.js',
                             'ui/app/assets/md/material-icons.css',
                             'ui/app/assets/Roboto/roboto.css',]},

    # metadata for upload to PyPI
    license="Copyright 2017, Abstrium SAS.  All rights reserved.",
    keywords=["pydio", "file", "sync", "synchronization"],
    url="http://pydio.com/",

    entry_points={'console_scripts': ['pydio = pydio.main:main']},
)
