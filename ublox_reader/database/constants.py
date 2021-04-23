#!/usr/bin/env python3
"""
Constants for DataBase

:author: Angelo Cutaia
:copyright: Copyright 2021, Angelo Cutaia
:license: Apache License 2.0
:version: 1.0.0

..

    Copyright 2021 Angelo Cutaia

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

# settings
from ..settings import config

# ------------------------------------------------------------------------------

# Module version
__version_info__ = (1, 0, 0)
__version__ = ".".join(str(x) for x in __version_info__)

# Documentation strings format
__docformat__ = "restructuredtext en"

# ------------------------------------------------------------------------------


############
# DATABASE #
############


DB_HOST = config.get("POSTGRESQL", "HOST")
"""Database host address"""

DB_PORT = config.getint("POSTGRESQL", "PORT")
""" Port number to connect to at the server host"""

DB_USER = config.get("POSTGRESQL", "USER")
"""The name of the user of the database used for authentication"""

DB = config.get("POSTGRESQL", "DB")
"""The name of the database to connect to"""

DB_PWD = config.get("POSTGRESQL", "PWD")
"""Password to be used for authentication"""

# ------------------------------------------------------------------------------


#############
# EXCEPTION #
#############


class DataBaseException(Exception):
    """Base class for database errors"""

    def __init__(self, *args, **kwargs):  # real signature unknown
        pass


# ------------------------------------------------------------------------------
