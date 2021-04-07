#!/usr/bin/env python3
"""
Tests the utilities module

:author: Angelo Cutaia
:copyright: Copyright 2021, Angelo Cutaia
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

# Standard library
import asyncio
from datetime import datetime
from functools import partial
from concurrent.futures import ThreadPoolExecutor

# Test
import pytest

# fast event loop
import uvloop

# utility methods
from ublox_reader.utilities import DataParser

# Test constants
from tests.constants import *

# ------------------------------------------------------------------------------


# Module version
__version_info__ = (1, 0, 0)
__version__ = ".".join(str(x) for x in __version_info__)

# Documentation strings format
__docformat__ = "restructuredtext en"


# ------------------------------------------------------------------------------

@pytest.fixture()
def event_loop():
    """
    Set uvloop as the default event loop
    """
    loop = uvloop.Loop()
    yield loop
    loop.close()


class TestUtilities:
    """
    Test the utilities methods
    """

    def test_adjust_second(self):
        """
        Test the time message utility adjust second
        """
        assert timestampMessage_unix == DataParser.adjust_second(
            ((raw_galWno * 604800 + raw_galTow) * 1000 + 935280000000) - (raw_leapS * 1000)
        ), "Error adjusting time"
        assert timestampMessage_galileo == DataParser.adjust_second((raw_galWno * 604800 + raw_galTow)), \
            "Error adjusting time"

    def test_read_auth_bits(self):
        """
        Test if the auth_bits were read correctly
        """
        # Test read_auth_bit utility
        assert DataParser.read_auth_bits(TEST_AUTH_BYTES) == 0, "For this payload the 40 bits must be all zero"

    def test_extract_galileo_data(self):
        """
        Test if the galileo data are extracted correctly
        """
        assert DataParser.extract_galileo_data(
            UBLOX_MESSAGE_PAYLOAD[12:44]
        ) == GALILEO_MESSAGE_PAYLOAD, "Error during the extraction"

    def test_parse_messages(self):
        """
        Test if the time message and the galileo message
        were parsed correctly
        """
        # Get the current year
        year = datetime.now().year

        # Instantiate Data Parser utility class
        data_parser = DataParser()

        # Analyze the data
        data_parser.parse_time_message(TIME_MESSAGE_PAYLOAD)
        table, data_to_store = data_parser.parse_message(UBLOX_MESSAGE_PAYLOAD)

        # Check if the data were parsed correctly
        assert table == f'{year}_Italy_{raw_svId}', "Error generating the table"
        # Check timestamp
        assert data_to_store[1] == timestampMessage_unix, "Wrong unix time stamp"
        # Check time of the week
        assert data_to_store[2] == raw_galTow, "raw_galTow wrong"
        # Check week number
        assert data_to_store[3] == raw_galWno, "raw_galWno wrong"
        # Check leap seconds
        assert data_to_store[4] == raw_leapS, "raw_leapS wrong"
        # Check ublox_data
        assert data_to_store[5] == UBLOX_MESSAGE_PAYLOAD.hex(), "Error converting the bytes in a hex string"
        # Check galileo_data
        assert data_to_store[6] == GALILEO_MESSAGE_PAYLOAD, "Error converting the bytes in a hex string"
        # Check auth_bits as integer
        assert data_to_store[7] == raw_auth, "Error converting auth_bits in a integer"
        # Check service id
        assert data_to_store[8] == raw_svId, "raw_svId wrong"
        # Check num words
        assert data_to_store[9] == raw_numWords, "raw_numWords wrong"
        # Check galileo checksum B
        assert data_to_store[10] == raw_ck_B, " Galileo raw_ck_B wrong"
        # Check galileo checksum A
        assert data_to_store[11] == raw_ck_A, "Galileo raw_ck_A wrong"
        # Check time checksum A
        assert data_to_store[12] == time_raw_ck_A, "Time raw_ck_A wrong"
        # Check time checksum B
        assert data_to_store[13] == time_raw_ck_B, "Time raw_ck_B wrong"
        # Check osnma
        assert data_to_store[14] == -1, "OSNMA wrong"
        # Check time stamp message
        assert data_to_store[15] == timestampMessage_galileo, "Wrong galileo timestamp"

    def test_meaconing_messages(self):
        """
        Test if the meaconing is detected well
        """
        # Instantiate Data Parser utility class
        data_parser = DataParser()
        data_parser.parse_clock_message(b'\x01"\x14\x00\x10\x0e0\x110j\n\x00\x99\x00\x00\x00\x08\x00\x00\x00g\x03\x00\x00E|')
        data_parser.parse_clock_message(b'\x01"\x14\x00\xf8\x110\x11\xc9j\n\x00\x99\x00\x00\x00\x08\x00\x00\x00\x8c\x03\x00\x00\xee\xf9')
        assert data_parser.attack is False, "Those data are consecutive"

        data_parser.parse_clock_message(b'\x01"\x14\x00`s\x93\x11\xff\xc1\xfe\xff\x10\xfb\xff\xff\x03\x00\x00\x00\x8d\x00\x00\x00\x046')
        assert data_parser.attack is True, "Those data aren't consecutive"
