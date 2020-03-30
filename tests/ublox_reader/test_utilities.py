#!/usr/bin/env python3
"""
Tests the utilities module

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
import pytest

# utility methods
from ublox_reader.utilities import adjust_second, parse_time_message, parse_message, read_auth_bits

# Test constants
from tests.constants import *

# ------------------------------------------------------------------------------


# Module version
__version_info__ = (1, 0, 0)
__version__ = ".".join(str(x) for x in __version_info__)

# Documentation strings format
__docformat__ = "restructuredtext en"


# ------------------------------------------------------------------------------


class TestUtilities:
    """
    Test the utilities methods
    """

    def test_adjust_second(self):
        """
        Test the time message utility adjust second
        """
        assert timestampMessage_unix == adjust_second(
            ((raw_galWno * 604800 + raw_galTow) * 1000 + 935280000000) - (raw_leapS * 1000)
        ), "Error adjusting time"
        assert timestampMessage_galileo == adjust_second((raw_galWno * 604800 + raw_galTow)), \
            "Error adjusting time"

    def test_read_auth_bits(self):
        """
        Test if the auth_bits were read correctly
        """
        # Test read_auth_bit utility
        assert read_auth_bits(TEST_AUTH_BYTES) == 0, "For this payload the 40 bits must be all zero"

    def test_parse_messages(self):
        """
        Test if the time message and the galileo message
        were parsed correctly
        """
        # Time message
        parse_time_message(TIME_MESSAGE[0:-2])
        # Galielo message
        result = parse_message(GALILEO_MESSAGE[0:-2])

        # Check timestamp
        assert result[1] == timestampMessage_unix, "Wrong unix time stamp"
        # Check time of the week
        assert result[2] == raw_galTow, "raw_galTow wrong"
        # Check week number
        assert result[3] == raw_galWno, "raw_galWno wrong"
        # Check leap seconds
        assert result[4] == raw_leapS, "raw_leapS wrong"
        # Check data
        assert result[5] == GALILEO_MESSAGE[0:-2].hex(), "Error converting the bytes in a hex string"
        # Check auth_bits as integer
        assert result[6] == 0, "Error converting auth_bits in a integer"
        # Check service id
        assert result[7] == raw_svId, "raw_svId wrong"
        # Check num words
        assert result[8] == raw_numWords, "raw_numWords wrong"
        # Check galileo checksum B
        assert result[9] == raw_ck_B, " Galileo raw_ck_B wrong"
        # Check galileo checksum A
        assert result[10] == raw_ck_A, "Galileo raw_ck_A wrong"
        # Check time checksum A
        assert result[11] == time_raw_ck_A, "Time raw_ck_A wrong"
        # Check time checksum B
        assert result[12] == time_raw_ck_B, "Time raw_ck_B wrong"
        # Check time stamp message
        assert result[13] == timestampMessage_galileo, "Wrong galileo timestamp"







