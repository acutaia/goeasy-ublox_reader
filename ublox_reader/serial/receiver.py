#!/usr/bin/env python3
"""
Asynchronous serial receiver for UbloxReader

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
import time
from asyncio import Event
from typing import AsyncIterable, Optional, Callable

# Asynchronous libraries
from uvloop import Loop
from aioserial import AioSerial, SerialException
from aiologger import Logger

# constants
from ublox_reader.serial.constants import *

# ------------------------------------------------------------------------------


# Module version
__version_info__ = (1, 0, 0)
__version__ = ".".join(str(x) for x in __version_info__)

# Documentation strings format
__docformat__ = "restructuredtext en"

# ------------------------------------------------------------------------------


###################
# SERIAL RECEIVER #
###################


class SerialReceiver(AioSerial):
    """
    A class that handles the serial connection of the
    Ubolox Receiver, reading the data following the
    format of the ublox communication protocol
    """
    def __init__(self, logger, receiver_stop, stop_method, loop):
        # type: (Logger, Event, Callable, Loop) -> None
        """
        Setup a SerialReceiver
        :param logger: asynchronous logger
        :param receiver_stop: asynchronous event used to stop the receiver
        :param stop_method: asynchronous method used to clean the connection
        :param loop: event loop
        """
        super().__init__(SERIAL_PORT, SERIAL_BAUDRATE, loop=loop)
        self.logger = logger  # type: Logger
        self.receiver_stop = receiver_stop  # type: Event
        self.stop = stop_method  # type: Callable

    @classmethod
    async def setup(cls, logger, receiver_stop, stop_method, loop):
        # type: (Logger, Event, Callable, Loop) -> Optional[SerialReceiver]
        """
        Instantiate a SerialReceiver instance and setup the serial connection
        sending the setup bytes to the ublox receiver
        :param logger: UbloxReceiver internal logger
        :param receiver_stop: UbloxReceiver internal event
        :param stop_method:  UbloxReceiver close_all_connections method
        :param loop: event loop
        :return: a SerialReceiver instance, if no exceptions during the setup, else return None
        """
        try:
            # Create an instance of SerialReceiver
            self = SerialReceiver(logger, receiver_stop, stop_method, loop)

            # SerialReceiver Logs
            self.logger.info("".join(
                [time.ctime(), ": UbloxReceiver: [Connection]: connected to ", SERIAL_PORT])
            )
            self.logger.info("".join(
                [time.ctime(), ": UbloxReceiver: [SerialReceiver]: sending setup bytes"])
            )

            # Set up serial communication
            await self.writelines_async(SETUP_BYTES)
            # Shutdown  serial writer executor cause we won't write anymore serial data
            self._write_executor.shutdown()

        except SerialException as error:
            # Log the exception
            await logger.error("".join(
                [time.ctime(), ": UbloxReceiver: [SerialPortError]: ", error.strerror])
            )
            # Set flag to stop the receiver
            receiver_stop.set()
            # Return None
            return None
        # Setup made correctly, return self
        return self

    async def ublox_message(self):
        # type: () -> AsyncIterable[bytearray]
        """
        Asynchronous generator that returns a ublox message, at every iteration, obtained
        reading data from the serial connection until a receiver_stop event is set.
        Every ublox message has this structure:

            * 6 bytes at the beginning
                * 2 bytes of delimeter: [0xB5, 0x62]
                * 4 bytes of usefull data
            * payload which length is equal to the value of bytes 5 and 6 read in little endian
            * 2 bytes at the end (checksum)

        Firstly: read and drop the first 2 bytes, after that, read and store 4 bytes.
        Secondly: calculate the length of the payload reading the last two bytes stored in little endian.
        Thirdly: read and store a number of bytes equal to the payload length plus the 2 bytes of checksum.
        Finally: return the ublox message
        :return: A ublox message
        """
        # Log the beginning fo reading data
        self.logger.info("".join(
            [time.ctime(), ": UbloxReceiver: [SerialReceiver]: start reading"])
        )
        while not self.receiver_stop.is_set():
            try:
                # Empty message
                message = bytearray()

                # Read the delimeter and discard it cause we don't need it
                await self.read_async(2)

                # Save the first useful data (4 bytes)
                message.extend(await self.read_async(4))

                # Save the payload of the message and the two final bytes (checksum)
                message.extend(await self.read_async((int.from_bytes(message[2:], byteorder="little") + 2)))
                # Give the message
                yield message

            except SerialException:
                # Log the exception
                await self.logger.error("".join(
                    [time.ctime(), ": UbloxReceiver: [SerialPortError]: read data failed"])
                )
                # Close all the connections
                await self.stop()
