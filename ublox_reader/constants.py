#!/usr/bin/env python3
"""
Constants for UbloxReceiver

:author: Angelo Cutaia
:copyright: Copyright 2020, Angelo Cutaia
:license: Apache License 2.0
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

config.read(os.path.join(os.path.abspath(os.path.dirname(__file__)), '..', 'ublox_config.ini'))
"""Read from configuration file"""

# ------------------------------------------------------------------------------


############
# DATABASE #
############


DB_HOST = config.get("POSTGRESQL", "HOST")
"""Database host address"""

DB_PORT = config.getint("POSTGRESQL", "PORT")
""" Port number to connect to at the server host"""

DB_USER = config.get("POSTGRESQL", "USER")
"""The name of the database role used for authentication"""

DB = config.get("POSTGRESQL", "DB")
"""The name of the database to connect to"""

DB_PW = config.get("POSTGRESQL", "PASSWD")
"""Password to be used for authentication"""

DB_QUERY = 'INSERT INTO public.messages (' \
           'receptiontime,' \
           'timestampmessage_unix,' \
           'raw_galtow,' \
           'raw_galwno,' \
           'raw_leaps,' \
           'raw_data,' \
           'raw_authbit,' \
           'raw_svid,' \
           'raw_numwords,' \
           'raw_ck_b,' \
           'raw_ck_a,' \
           'raw_ck_a_time,' \
           'raw_ck_b_time,' \
           'timestampmessage_galileo' \
           ') VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14);'
"""Query to insert data in the database"""
