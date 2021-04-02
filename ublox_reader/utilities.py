#!/usr/bin/env python3
"""
Utility methods for Ublox Receiver

:author: Angelo Cutaia
:copyright: Copyright 2021, Angelo Cutaia
:version: 1.0.0.

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

# standard library
from datetime import datetime
import logging
import time
from typing import Union

# bit utilities
from bitarray import bitarray

# settings
from .settings import config


# ------------------------------------------------------------------------------


# Module version
__version_info__ = (1, 0, 0)
__version__ = ".".join(str(x) for x in __version_info__)

# Documentation strings format
__docformat__ = "restructuredtext en"

# ------------------------------------------------------------------------------


###############
# DATA PARSER #
###############


class DataParser:
    """
    A utility class which scope is to extract
    information from the ublox_messages
    """

    # Where the serial receiver is physically connected
    nation: str = config.get("COUNTRY", "NATION")

    # Time constants
    year: int = None
    reception_time: float = None
    timestamp_message_unix: float = None
    timestamp_message_galileo: int = None

    # Galielo
    raw_gal_tow: int = None
    raw_gal_wno: int = None
    raw_leap_s: int = None

    # Checksum
    time_raw_ck_a: int = None
    time_raw_ck_b: int = None

    # Meaconing
    threshold = config.get("THRESHOLD", "MEACONING_TH")
    drift: int = None
    bias: int = None
    attack: bool = False

    def parse_time_message(self, data: bytes) -> None:
        """
        The time of the message reception is not the same time written
        inside the message. The scope of this function is to analise and
        store the information inside it's attributes in order to merge it
        with galileo message to fill the tuple of data to store

        :param data: Bytes to parse
        """
        # Save the time of the message reception
        self.year = datetime.now().year
        self.reception_time = time.time() * 1000  # expressed in ms

        # Read RAW data from the message
        self.raw_gal_tow = int.from_bytes(data[8:12], byteorder="little")
        self.raw_gal_wno = int.from_bytes(data[16:18], byteorder="little")
        self.raw_leap_s = data[18]
        self.time_raw_ck_a = data[24]
        self.time_raw_ck_b = data[25]

        # Compute time using all the data read from raw data
        self.timestamp_message_unix = DataParser.adjust_second(
            ((self.raw_gal_wno * 604800 + self.raw_gal_tow) * 1000 + 935280000000)
            - (self.raw_leap_s * 1000)
        )  # (expressed in ms)

        self.timestamp_message_galileo = DataParser.adjust_second(
            (self.raw_gal_wno * 604800 + self.raw_gal_tow)
        )

    def parse_clock_message(self, data: bytes) -> None:
        """
        Parse the clock message to detect meaconing attacks

        :param data: clock message
        :return:
        """

        # Check if we already received a message
        if self.bias and self.drift:
            current_drift = data[11]
            current_bias = data[7]

            # Attack attack false condition
            if current_drift < self.threshold and (
                    abs(current_bias - self.bias) < self.threshold
                    or (
                        (1000 - self.threshold)
                        < abs(current_bias - self.bias)
                        < 1000 + self.threshold
                    )

            ):
                self.attack = False

            else:
                self.attack = True

            # Update bias and drift
            self.bias = current_bias
            self.drift = current_drift

        else:
            # first clock message received
            self.bias = data[7]
            self.drift = data[11]

    @staticmethod
    def adjust_second(seconds: Union[float, int]) -> Union[float, int]:
        """
        Utility method to adjust reception time

        :param seconds: Time of the received message
        :return: Correct reception time
        """
        # TODO: try and test -3 and -2 or -2 and -1
        #  (reception time is more than the real time). Messages are retrived each seconds,
        #  but ublox send message every second, divided at odd or even seconds.
        #  --> ask to GIANLUCA
        if seconds % 2 == 0:
            return seconds - 3
        else:
            return seconds - 2

    def parse_message(self, data: bytes) -> Union[str, tuple]:
        """
        Method to extract data from the GALILEO message and
        combine them with the values of the time message. After the data
        are extracted, generate the database table name that will contain them
        and the tuple of data to store.

        :param data: bytes to analise
        :return: Table name and the tuple of data to store
        """

        # Read all data
        raw_sv_id = data[5]
        # auth bit are encoded in 8 bytes from byte 28 to byte 36
        raw_auth_bits = DataParser.read_auth_bits(data[28:36])
        raw_num_words = data[8]
        raw_ck_a = data[-2]
        raw_ck_b = data[-1]
        # Galileo Data are encoded from byte 12 to byte 44
        galileo_data = DataParser.extract_galileo_data(data[12:44])

        # Check if we are under attack
        if self.attack:
            authenticity = 0
        else:
            # Unknown authenticity cause we have to check OSNMA
            authenticity = -1

        # TODO: currently not needed data
        #  const reserved1 = data[6]
        #  const freqId = data[7]
        #  const chn = data[9]
        #  const version = data[10]
        #  const reserved2 = data[11]
        #  const size = int.from_bytes(data[2:4], byteorder="little")

        # Return the table name and the tuple of data to store
        return f"{self.year}_{self.nation}_{raw_sv_id}", (
            self.reception_time,
            self.timestamp_message_unix,
            self.raw_gal_tow,
            self.raw_gal_wno,
            self.raw_leap_s,
            data.hex(),
            galileo_data,
            raw_auth_bits,
            raw_sv_id,
            raw_num_words,
            raw_ck_b,
            raw_ck_a,
            self.time_raw_ck_a,
            self.time_raw_ck_b,
            authenticity,
            self.timestamp_message_galileo,
        )

    @staticmethod
    def read_auth_bits(data: bytes) -> int:
        """
        Utility method to retrieve only auth bits from the entire data string

        :param data: The 8 bytes to analise
        :return: An integer which represents the 40 auth bits
        """
        # Initialize the array
        auth_bits = bitarray(endian="little")

        # get the 64 bits
        auth_bits.frombytes(data)

        # isolate the 40 auth bits
        del auth_bits[14:38]

        # return the value of those 40 bits as an integer
        return int.from_bytes(auth_bits.tobytes(), byteorder="little")

    @staticmethod
    def extract_galileo_data(data: bytes) -> str:
        """
        Utility method to extract galileo data from ublox message

        :param data: payload
        :return: bytes in hex format
        """
        # Invert the data and remove the padding
        wordA = data[3::-1]
        wordB = data[7:3:-1]
        wordC = data[11:7:-1]
        wordD = data[15:12:-1]  # padding removed
        wordE = data[19:15:-1]
        wordF = data[23:19:-1]
        wordG = data[27:23:-1]
        wordH = data[31:28:-1]  # padding removed

        # generate the galileo data
        galileo_data = wordA + wordB + wordC + wordD + wordE + wordF + wordG + wordH

        return galileo_data.hex()


# ------------------------------------------------------------------------------


##########
# LOGGER #
##########


class UbloxLogger:
    """
    A utility class which scope is to configure
    the logging of the application
    """

    @staticmethod
    def get_logger(name: str) -> logging.Logger:
        """
        Setup the logger instance

        :param name: Name of the logger
        :return: An instance of the standard library logger
        """
        # create logger
        logger = logging.getLogger(name)
        logger.setLevel(logging.INFO)

        # create console handler and set level to debug
        ch = logging.StreamHandler()
        ch.setLevel(logging.INFO)

        # create formatter
        formatter = logging.Formatter("%(levelname)s : [%(name)s] : %(message)s")

        # add formatter to ch
        ch.setFormatter(formatter)

        # add ch to logger
        logger.addHandler(ch)

        return logger
