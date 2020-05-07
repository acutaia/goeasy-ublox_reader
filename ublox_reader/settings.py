#!/usr/bin/env python3
"""
Settings for Ublox Reader package

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

# Standard library
import configparser
import os

# ------------------------------------------------------------------------------

# Module version
__version_info__ = (1, 0, 0)
__version__ = ".".join(str(x) for x in __version_info__)

# Documentation strings format
__docformat__ = "restructuredtext en"

# ------------------------------------------------------------------------------


############
# SETTINGS #
############

config = configparser.ConfigParser()
"""Config object"""

DEV_PATH = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'config/ublox_config.ini')
"""Path for the configuration file in developer mode"""

USER_PATH = "/etc/ublox-reader/config/ublox_config.ini"
"""Path for the configuration file in user mode"""

config.read((DEV_PATH, USER_PATH))
"""Read from configuration file"""
