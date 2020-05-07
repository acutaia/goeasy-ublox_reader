#!/usr/bin/env python3
"""
Ublox Reader app entry point

:author: Angelo Cutaia
:copyright: Copyright 2020, Angelo Cutaia
:version: 1.0.0

..

    Copyright 2020 Angelo Cutaia

    Licensed under the Apache License, Version 2.0 (the "License");
    you may not use this file except in compliance with the License.
    You may obtain a copy of the License at

        http://www.apache.org/licenses/LICENSE-2.0

    Unless required by applicable law or agreed to in writing, software
    distributed under the License is distributed on an "AS IS" BASIS,
    WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
    See the License for the specific language governing permissions and
    limitations under the License.
"""

from setuptools import setup, find_packages
from os import path

this_directory = path.abspath(path.dirname(__file__))
with open(path.join(this_directory, 'README.md'), encoding='utf-8') as f:
    long_description = f.read()

VERSION = "1.0.0"

setup(
    version=VERSION,
    name="ublox-reader",
    author="Angelo Cutaia",
    author_email="angelo.cutaia@linksfoundation.com",
    license="Apache Software License (Apache Software License 2.0)",
    description="Package that handles a ublox receiver",
    url="",
    long_description=long_description,
    long_description_content_type="text/markdown",
    python_requires=">=3.7",
    packages=find_packages(include=['ublox_reader', 'ublox_reader.*']),
    install_requires=[
        'aiologger>=0.5.0',
        'aioserial>=1.2.3',
        'asyncpg>=0.20.1',
        'bitarray>=1.2.1',
        'uvloop>=0.14.0',
    ],
    include_package_data=True,
    download_url='',
    entry_points={
        'console_scripts': [
            'ublox-reader = ublox_reader.ublox_receiver:UbloxReceiver.run'
        ]},
    data_files=[
        (path.expanduser("/etc/ublox-reader/config/"), ["ublox_reader/config/*"])
    ]
)
