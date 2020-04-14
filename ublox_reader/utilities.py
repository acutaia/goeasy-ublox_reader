#!/usr/bin/env python3
"""
Utility methods for Ublox Receiver

:author: Angelo Cutaia
:copyright: Copyright 2020, Angelo Cutaia
:version: 1.0.0.

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

# standard library
import asyncio
import time
from typing import Callable
from contextvars import ContextVar
# uvloop event loop
from uvloop import Loop


# ------------------------------------------------------------------------------


# Module version
__version_info__ = (1, 0, 0)
__version__ = ".".join(str(x) for x in __version_info__)

# Documentation strings format
__docformat__ = "restructuredtext en"

# ------------------------------------------------------------------------------


##############
# BYTES MASK #
##############


LSB_MASK = bytes([0x00, 0x00, 0x3F, 0xFF])
"""Least significant bit mask"""

MSB_MASK = bytes([0xFF, 0xFF, 0xFF, 0xC0])
"""Most significant bit mask"""

# ------------------------------------------------------------------------------


#####################
# TIME MESSAGE VARS #
#####################


receptionTime = ContextVar("time.receptionTime", default=0)
"""Reception time of the message"""

receptionTimeHumanReadableFormat = ContextVar("time.receptionTimeHumanReadableFormat", default=0)
"""Reception time in human readable format"""

raw_galTow = ContextVar("time.raw_galTow", default=0)
"""Galielo time of the week"""

raw_galWno = ContextVar("time.raw_galWno", default=0)
"""Galielo week number"""

raw_leapS = ContextVar("time.raw_leapS", default=0)
"""Galileo leap seconds"""

time_raw_ck_A = ContextVar("time.raw_ck_A", default=0)
"""Checksum A"""

time_raw_ck_B = ContextVar("time.raw_ck_B", default=0)
"""Checksum B"""

timestampMessage_unix = ContextVar("time.timestampMessage_unix", default=0)
"""Time stamp of the message in unix"""

timestampMessage_galileo = ContextVar("time.timestampMessage_galileo", default=0)
"""Time stamp of the message in galileo"""

timestampMessage_unixHumanReadable = ContextVar("time.timestampMessage_unixHumanReadable", default=0)
"""Time stamp of unix in a readable format"""

# ------------------------------------------------------------------------------


############################
# TIME UTILITIES FUNCTIONS #
############################


def parse_time_message(data: bytes) -> None:
    """
    The time of the message reception is not the same time written
    inside the message. The scope of this function is to analise and
    store the information inside the contextvars

    :param data: Bytes to parse
    """
    # Save the time of the message reception
    receptionTime.set(time.time())
    receptionTimeHumanReadableFormat.set(time.ctime(receptionTime.get()))

    # Read RAW data from the message
    raw_galTow.set(int.from_bytes(data[8:12], byteorder="little"))
    raw_galWno.set(int.from_bytes(data[16:18], byteorder="little"))
    raw_leapS.set(data[18])
    time_raw_ck_A.set(data[24])
    time_raw_ck_B.set(data[25])

    # Compute time using all the data read from raw data
    timestampMessage_unix.set(
        adjust_second(
            ((raw_galWno.get() * 604800 + raw_galTow.get()) * 1000 + 935280000000) - (raw_leapS.get() * 1000)
        )
    )
    timestampMessage_galileo.set(adjust_second((raw_galWno.get() * 604800 + raw_galTow.get())))

    # Save also time in human readable format ( time.ctime accepts only seconds)
    timestampMessage_unixHumanReadable.set(time.ctime(timestampMessage_unix.get()/1000))


def adjust_second(seconds: float) -> float:
    """
    Utility function to adjust reception time

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


# ------------------------------------------------------------------------------


###############################
# GALILEO UTILITIES FUNCTIONS #
###############################


def parse_message(store_data: Callable, loop: Loop, data: bytes) -> None:
    """
    Utility function to extract data from the GALILEO message and
    combine them with the values of the time message stored inside
    the contextvars. When the data are obtained, schedule the store_data
    coroutine in the event loop

    :param store_data: Coroutine to store data
    :param loop: Event Loop
    :param data: bytes to analise
    """
    # Read all data
    raw_sv_id = data[5]
    # auth bit are encoded in 8 bytes from byte 28 to byte 36
    raw_auth_bits = read_auth_bits(data[28:36])
    raw_num_words = data[8]
    raw_ck_a = data[48]
    raw_ck_b = data[49]

    # TODO: currently not needed data
    #  const reserved1 = data[6]
    #  const freqId = data[7]
    #  const chn = data[9]
    #  const version = data[10]
    #  const reserved2 = data[11]
    #  const size = int.from_bytes(data[2:4], byteorder="little")

    # Schedule
    asyncio.run_coroutine_threadsafe(
        store_data(
            (
                receptionTime.get(),
                timestampMessage_unix.get(),
                raw_galTow.get(),
                raw_galWno.get(),
                raw_leapS.get(),
                data.hex(),
                raw_auth_bits,
                raw_sv_id,
                raw_num_words,
                raw_ck_b,
                raw_ck_a,
                time_raw_ck_A.get(),
                time_raw_ck_B.get(),
                timestampMessage_galileo.get()
            )
        ), loop
    )


def read_auth_bits(data: bytes) -> int:
    """
    Utility function to retrieve only auth bits from the entire data string

    :param data: The 8 bytes to analise
    :return: An integer which represents the 40 auth bits
    """
    # Read the MSB and LSB
    lsb_num = data[0:4]
    msb_num = data[4:]

    # Perform bitwise AND in order to isolate only the 40 auth bits
    lsb_auth = bytes(
        [
            lsb_num[i] & LSB_MASK[i]
            for i in range(0, 4)
        ]
    )
    msb_auth = bytes(
        [
            msb_num[i] & MSB_MASK[i]
            for i in range(0, 4)
        ]
    )

    # Convert the binary string in an integer
    return int(
        # Convert the 40 auth bits in a binary string

        # Beginning of the most significant auth bits
        f"{bin(msb_auth[3])[2:].zfill(8)}"
        f"{bin(msb_auth[2])[2:].zfill(8)}"
        f"{bin(msb_auth[1])[2:].zfill(8)}"
        # Ending of the most significant auth bits
        f"{bin(msb_auth[0])[2:].zfill(8)[0:2]}"

        # Beginning of the least significant auth bits
        f"{bin(lsb_auth[1])[2:].zfill(8)}"
        # Ending of the least significant auth bits
        f"{bin(lsb_auth[0])[2:].zfill(8)[0:6]}"
        , 2  # Use 2 cause it's a binary string
    )
