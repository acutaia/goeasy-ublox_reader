"""
Asynchronous serial receiver for UbloxReader

:author: Angelo Cutaia
:copyright: Copyright 2021, LINKS Foundation
:version: 1.0.0

..

    Copyright 2021 LINKS Foundation

    Licensed under the Apache License, Version 2.0 (the "License");
    you may not use this file except in compliance with the License.
    You may obtain a copy of the License at

        https://www.apache.org/licenses/LICENSE-2.0

    Unless required by applicable law or agreed to in writing, software
    distributed under the License is distributed on an "AS IS" BASIS,
    WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
    See the License for the specific language governing permissions and
    limitations under the License.
"""

# Standard library
from logging import Logger
from typing import AsyncIterable

# Asynchronous libraries
from aioserial import AioSerial, SerialException
from uvloop import Loop

# constants
from .constants import (
    SERIAL_PORT,
    SETUP_BYTES,
    SERIAL_BAUDRATE,
    DELIMETER,
    UbloxSerialException,
)

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

    def __init__(self, logger: Logger, loop: Loop, port: str, baudrate: int) -> None:
        """
        Setup a SerialReceiver

        :param logger: Asynchronous logger
        :param loop: Event loop
        :param port: Serial port used by the receiver
        :param baudrate: Baudrate of the connection
        """
        super().__init__(port=port, baudrate=baudrate, loop=loop)
        self.logger = logger  # type: Logger
        # reading flag
        self.start_reading = False  # type: bool

        # ublox-message flags
        self.first_ublox_message_after_cleaning = False
        self.ublox_messages = False
        self.cleaning_ublox_buffer = True
        self.ublox_counter = 0

    @classmethod
    async def setup(cls, logger, loop, port=SERIAL_PORT, baudrate=SERIAL_BAUDRATE):
        # type: (Logger, Loop, str, int) -> SerialReceiver
        """
        Instantiate a SerialReceiver instance and setup the serial connection
        sending the setup bytes to the ublox receiver

        :param logger: UbloxReceiver internal logger
        :param loop: Event loop
        :param port: Serial port used by the receiver
        :param baudrate: Baudrate of the connection
        :return: A SerialReceiver instance
        """
        try:
            # Create an instance of SerialReceiver
            self = SerialReceiver(logger, loop, port, baudrate)

            # SerialReceiver Log
            self.logger.info(f"connected to {self.port}")

            # Set up serial communication
            await self.writelines_async(SETUP_BYTES)
            # Log
            self.logger.info("setup bytes send")
            # Shutdown  serial writer executor cause we won't write anymore serial data
            self._write_executor.shutdown()

        except SerialException as error:
            # Log the exception
            logger.error(f"{error.strerror}")
            # Set flag to stop the receiver
            raise UbloxSerialException
        # Setup made correctly, return self
        return self

    async def ublox_message(self) -> AsyncIterable[bytes]:
        """
        Asynchronous generator
        that returns a ublox message at every iteration.

        Every ublox message frame has this structure:

            -  **6 bytes** at the beginning:

                -   2-bytes **Preamble** consisting of two synchronization characters: **0xB50x62**

                -   1-byte Message **Class** field follows. A Class is a group of messages
                    that are related to each other

                -   1-byte Message **ID** field defines the message that is to follow

                -   2-bytes **Length** field follows. The length is defined as being that of the **payload** only.
                    It does not include the Preamble, Message Class, Message ID, Length, or CRC fields.
                    The number format of the length field is a Little-Endian unsigned 16-bit integer

            -  **N** bytes of **Payload** with  N equal to the number format of the field **Length**
            -  **2 bytes** of checksum:

                - 1-byte **CK_A**

                - 1-byte **CK_B**

        The work done by the asynchronous generator can be divided in 4 steps:

            **1.** read and drop the **Preamble**

            **2.** read and store 4 bytes:
                    - 1-byte Message **Class**
                    - 1-byte Message **ID**
                    - 2-byte Message **Length**

            **3.** read and store a number of bytes equal to the length of the payload + the 2 bytes of checksum.

            **4.** return the ublox message

        :return: A ublox message
        """
        if not self.start_reading:
            # Log the beginning fo reading data
            self.logger.info("start reading")
            # set the flag
            self.start_reading = True

        try:

            # Check if we need to clean the buffer
            if self.cleaning_ublox_buffer:
                # Version 8 of ublox receiver has some incorrect buffer data sent after the setup

                # Remove the delimeter
                message = bytes(await self.read_until_async(DELIMETER))[:-2]
                len_message = len(message)

                # Check if the message has an acceptable size
                while len_message < 24:
                    message = bytes(await self.read_until_async(DELIMETER))[:-2]
                    len_message = len(message)

                # Give the message
                yield message

                # Increase the number of correct sent messages
                self.ublox_counter += 1

                # Check if we sent at least 5 correct messages
                if self.ublox_counter == 5:

                    # Set the flags
                    self.cleaning_ublox_buffer = False
                    self.first_ublox_message_after_cleaning = True
                    return

            # Check the status of this message
            elif self.first_ublox_message_after_cleaning:
                # This message doesn't have the delimeter at the beginning cause it was cleaned with the buffer

                # Empty message
                message = bytearray()
                # Save the first useful data (4 bytes)
                message.extend(await self.read_async(4))

                # Save the payload of the message and the two final bytes (checksum)
                message.extend(
                    await self.read_async(
                        (int.from_bytes(message[2:], byteorder="little") + 2)
                    )
                )
                # Give the message
                yield bytes(message)

                # Set the flags
                self.first_ublox_message_after_cleaning = False
                self.ublox_messages = True

                return

            # Check if the messages are already cleaned
            elif self.ublox_messages:
                # Empty message
                message = bytearray()

                # Read the Preamble and discard it cause we don't need it
                await self.read_async(2)

                # Save the first useful data (4 bytes)
                message.extend(await self.read_async(4))

                # Save the payload of the message and the two final bytes (checksum)
                message.extend(
                    await self.read_async(
                        (int.from_bytes(message[2:], byteorder="little") + 2)
                    )
                )
                # Give the message
                yield bytes(message)

        except SerialException as error:
            # Raise exception
            raise UbloxSerialException(f"[Serial] : {error.args[0]}")

    async def stop_serial(self) -> None:
        """
        Method to stop the SerialReceiver
        """
        # Close the serial port
        self.close()
        # Shutdown  serial reader  executor
        self._read_executor.shutdown(wait=False)
        # Log
        self.logger.info(f"disconnected from {self.port}")
