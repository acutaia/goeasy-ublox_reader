#!/usr/bin/env python3
"""
Test constants

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
import os
import time

FAKE_DATA = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'fake_data.txt')
"""Path of the file containing the fake data"""

# ------------------------------------------------------------------------------

# Module version
__version_info__ = (1, 0, 0)
__version__ = ".".join(str(x) for x in __version_info__)

# Documentation strings format
__docformat__ = "restructuredtext en"

# ------------------------------------------------------------------------------


########
# TIME #
########


TIME_MESSAGE_PAYLOAD = bytes([0x1, 0x25, 0x14, 0x0, 0x0, 0x16, 0x9C, 0x16, 0xC0, 0xC9, 0x5, 0x0, 0x1C, 0xA4, 0x2, 0x0,
                             0x31, 0x4, 0x12, 0x7, 0x3, 0x0, 0x0, 0x0, 0xA3, 0xEF, 0xB5, 0x62])
"""Time message payload with the delimeter [0xB5, 0x62] at the end"""

raw_galTow = 379328
"""Galielo time of the week"""

raw_galWno = 1073
"""Galielo week number"""

raw_leapS = 18
"""Galileo leap seconds"""

timestampMessage_unix = 1584609709.997
"""Time stamp of the message in a unix system"""

timestampMessage_galileo = 649329725
"""Time stamp of the message in galileo"""

time_raw_ck_A = 163
"""Time checksum A"""

time_raw_ck_B = 239
"""Time checksum B"""

# ------------------------------------------------------------------------------


###########
# GALILEO #
###########


GALILEO_MESSAGE_PAYLOAD = bytes([0x2, 0x13, 0x2C, 0x0, 0x2, 0x12, 0x1, 0x0, 0x9, 0xE, 0x2, 0xD2, 0x34, 0x77, 0x76, 0x7,
                                 0x5D, 0x63, 0x0, 0x1, 0xF5, 0x51, 0x22, 0x24, 0x0, 0x40, 0xF, 0x7F, 0x0, 0x40, 0x65,
                                 0xA6, 0x2A, 0x0, 0x0, 0x0, 0xD2, 0x57, 0xAA, 0xAA, 0x0, 0x40, 0xBF, 0x3F, 0xD5, 0x9A,
                                 0xE8, 0x3F, 0x4A, 0x7C, 0xB5, 0x62])
"""Galileo message payload with the delimeter [0xB5, 0x62] at the end"""

TEST_AUTH_BYTES = bytes([0x0, 0x40, 0x65, 0xA6, 0x2A, 0x0, 0x0, 0x0])
"""Bytes that contain inside the 40 auth bits"""

raw_auth = 0
"""Int value of the 5 authorization bytes"""

raw_svId = 18
"""Galielo service id"""

raw_numWords = 9
"""Num of words"""

raw_ck_A = 74
"""Galileo checksum A"""

raw_ck_B = 124
"""Galileo checksum B"""

# ------------------------------------------------------------------------------


#################
# DATA TO STORE #
#################


DATA_TO_STORE = (
    time.time(),
    timestampMessage_unix,
    raw_galTow,
    raw_galWno,
    raw_leapS,
    GALILEO_MESSAGE_PAYLOAD.hex(),
    0,
    raw_svId,
    raw_numWords,
    raw_ck_B,
    raw_ck_A,
    time_raw_ck_A,
    time_raw_ck_B,
    timestampMessage_galileo
)
"""Data to use to test the database"""
