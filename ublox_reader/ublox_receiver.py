"""
Asynchronous Ublox Receiver

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
import asyncio
import signal
from logging import Logger
from typing import Union, Dict, Any

# Asynchronous libraries
import uvloop

# Ublox
from .database.postgresql import DataBase
from .serial.receiver import SerialReceiver
from .database.constants import DataBaseException
from .serial.constants import UbloxSerialException
from .utilities import DataParser, UbloxLogger


# Substitute asyncio loop with uvloop
uvloop.install()

# ------------------------------------------------------------------------------


# Module version
__version_info__ = (1, 0, 0)
__version__ = ".".join(str(x) for x in __version_info__)

# Documentation strings format
__docformat__ = "restructuredtext en"

# ------------------------------------------------------------------------------


##################
# UBLOX RECEIVER #
##################


class UbloxReceiver:
    """
    A class that handles the Ublox Receiver
    inserting in a PostgreSQL db the data
    retrieved from the serial connection
    """

    # Data_to_store tuple
    data_to_store: tuple = None
    # Connection pool to the db
    db: DataBase = None
    # Logger
    logger: Logger = UbloxLogger.get_logger("UbloxReceiver")
    # Serial transmission
    serial: SerialReceiver = None

    def __init__(self, loop: uvloop.Loop) -> None:
        """
        Set up UbloxReader

        :param loop: Asynchronous event loop implementation provided by uvloop
        """
        # utility class
        self.parser = DataParser()
        # event loop
        self.loop = loop
        # flag to notify the reception of a time message
        self.time_flag = False
        # queue containing the data to parse
        self.data_to_parse = asyncio.Queue()

    @staticmethod
    def run() -> None:
        """
        Setup a Ublox Receiver and starts to get the data. In
        case of a keyboard interrupt, stop the Reader and cleanup
        gracefully
        """
        # Get a new instance of the Event Loop
        loop = asyncio.get_event_loop()

        # OS signals to stop the receiver
        signals = (signal.SIGHUP, signal.SIGTERM, signal.SIGINT, signal.SIGQUIT)

        try:
            # Setup the Reader
            ublox_reader: UbloxReceiver = loop.run_until_complete(
                UbloxReceiver.set_up(loop)
            )

        except (DataBaseException, UbloxSerialException):
            # Something went wrong
            loop.run_until_complete(UbloxReceiver.shut_down())
            loop.close()
            return

        # Add signals handler to close gracefully the receiver
        for s in signals:
            loop.add_signal_handler(
                s, lambda x=s: asyncio.create_task(ublox_reader.close_all_connections())
            )

        # Set an exception handler to deal with the raised exceptions
        loop.set_exception_handler(ublox_reader.handle_exception)
        try:
            # Schedule get_data and parse data
            loop.create_task(ublox_reader.get_data())

            # Get data, parse and store until a OS signal
            loop.run_forever()
        finally:
            # Disconnect
            loop.close()

    @classmethod
    async def set_up(cls, loop):
        # type: (Union[uvloop.Loop, asyncio.AbstractEventLoop]) -> UbloxReceiver
        """
        Instantiate a UbloxReceiver instance and setup the serial receiver
        and the connection pool to the db

        :param loop:  Asynchronous event loop implementation provided by uvloop
        :return: A UbloxReceiver instance
        """
        # Create an instance of UbloxReader
        self = UbloxReceiver(loop)

        # Setup database
        self.db = await DataBase.setup(UbloxLogger.get_logger("DataBase"), loop)

        # Setup serial connection
        self.serial = await SerialReceiver.setup(UbloxLogger.get_logger("Serial"), loop)

        # Setup made correctly, return self
        return self

    async def get_data(self) -> None:
        """
        Read data from serial connection until obtain a ublox message.
        Once a message is obtained, put it in the queue of the
        data to parse
        """
        while True:
            async for message in self.serial.ublox_message():
                # Put the message in a queue to parse it
                self.loop.create_task(self.parse_data(message))

    async def parse_data(self, data: bytes) -> None:
        """
        Parse data received from the serial connection, the data that are
        useful are only Time messages and Galileo messages. In case of one
        of those messages, analyze them in an executor. Parse Galileo data only if
        a Time message was already received. Then schedule the storing of useful data in the database
        """
        # This is a TIME message
        if data[0] == 1 and data[1] == 37:
            # Set the received time message flag
            self.time_flag = True
            # Analyze the message in a executor
            self.parser.parse_time_message(data)
            return

        # This is a CLOCK message
        elif data[0] == 1 and data[1] == 34 and self.time_flag:
            self.parser.parse_clock_message(data)
            return

        # This is a GNSS message
        elif data[0] == 2 and self.time_flag:
            # Check if it's a GALILEO message
            # {GPS: 0}, {SBUS: 1}, {GALILEO: 2}, {BEIDU: 3}, {IMES: 4}, {QZSS: 5}, {GLONASS: 6}
            if data[4] == 2:
                # Analyze the message in a executor and scheduling the storing of the data
                table_name, data_to_store = self.parser.parse_message(data)
                await self.db.store_data(table_name, data_to_store)
                # TODO: if not self.parser.attack convolution

    def handle_exception(self, loop, context):
        # type: (Union[asyncio.AbstractEventLoop, uvloop.Loop], Dict[str, Any]) -> None
        """
        Default handler for all the exceptions raised during the execution with the
        purpose of logging them and schedule the cleanup of the loop.

        :param loop: Event Loop
        :param context: Dict containing the details of the exception
        """
        # context["message"] will always be there; but context["exception"] may not
        msg = context.get("exception", context["message"])

        # Schedule the cleanup of the loop
        loop.create_task(self.close_all_connections(msg=msg))

    async def close_all_connections(self, msg: str = None) -> None:
        """
        Close gracefully all the connections

        :param msg = Message of the serious exception
        """
        # Check if there was an exception
        if msg:
            # Log the exception
            self.logger.error(msg)

        # Log the closing of all the connections
        self.logger.warning("closing all connections")

        # Cancel all pending tasks
        await self.shut_down()

        # Close serial connection
        await self.serial.stop_serial()

        # Close database
        await self.db.close()

        # Log the exit from the application
        self.logger.info("shutdown completed")

        # Stop the loop
        self.loop.stop()

    @staticmethod
    async def shut_down() -> None:
        """
        Cancel all pending tasks
        """
        # Pending tasks
        pending = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]

        # Cancel all pending tasks
        [task.cancel() for task in pending]

        # Wait for all pending tasks to be cancelled
        await asyncio.gather(*pending, return_exceptions=True)
