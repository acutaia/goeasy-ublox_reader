#!/usr/bin/env python3
"""
Dummy UbloxReceiver class for testing

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
import signal
import asyncio
from functools import partial
from typing import Union

# Asynchronous libraries
from aiologger.logger import Logger, LogLevel
from uvloop import Loop

# Ublox
from ublox_reader.ublox_receiver import UbloxReceiver
from tests.ublox_reader.serial.fake_serial import FakeSerialReceiver
from tests.ublox_reader.database.dummy import DummyDataBase
from ublox_reader.utilities import parse_message
# Exceptions
from ublox_reader.serial.constants import UbloxSerialException
from ublox_reader.database.constants import DataBaseException

# ------------------------------------------------------------------------------


# Module version
__version_info__ = (1, 0, 0)
__version__ = ".".join(str(x) for x in __version_info__)

# Documentation strings format
__docformat__ = "restructuredtext en"


# ------------------------------------------------------------------------------


###############
# DUMMY UBLOX #
###############


class DummyUblox(UbloxReceiver):
    """
    A class that simulates the behaviour of
    the UbloxReceiver
    """
    @classmethod
    def run(cls):
        """
        Setup a Ublox Receiver and starts to get the data. In
        case of a keyboard interrupt, stop the Reader and cleanup
        gracefully
        """
        # Get a new instance of the Event Loop
        loop = asyncio.new_event_loop()
        # Set as the default loop of this thread
        asyncio.set_event_loop(loop)

        # OS signals to stop the receiver
        signals = (signal.SIGHUP, signal.SIGTERM, signal.SIGINT, signal.SIGQUIT)

        try:
            # Setup the Reader
            ublox_reader: UbloxReceiver = loop.run_until_complete(DummyUblox.set_up(loop))

        except (DataBaseException, UbloxSerialException):
            # Something went wrong
            loop.run_until_complete(DummyUblox.shut_down())
            loop.close()
            return

        # Add signals handler to close gracefully the receiver
        for s in signals:
            loop.add_signal_handler(
                s, lambda sig=s: asyncio.create_task(ublox_reader.close_all_connections()))

        # Set an exception handler to deal with the raised exceptions
        loop.set_exception_handler(ublox_reader.handle_exception)
        try:
            # Schedule the stop of the execution
            loop.call_later(30, DummyUblox.stop_test)
            # Schedule get_data and parse data
            loop.create_task(ublox_reader.get_data())
            loop.create_task(ublox_reader.parse_data())

            # Get data, parse and store until a OS signal
            loop.run_forever()
        finally:
            # Disconnect
            loop.close()

    @classmethod
    async def set_up(cls, loop):
        # type: (Union[Loop, asyncio.AbstractEventLoop]) -> UbloxReceiver
        """
        Instantiate a UbloxReceiver instance and setup the serial receiver
        and the connection pool to the db

        :param loop:  Asynchronous event loop implementation provided by uvloop
        :return: A UbloxReceiver instance
        """
        # Create an instance of UbloxReader
        self = DummyUblox(loop)

        # Instantiate logger
        self.logger = Logger.with_default_handlers(level=LogLevel.INFO)
        # disable for testing purpose
        self.logger.disabled = True

        # Link UbloxReceiver attributes and methods to Database.setup class method
        database_setup = partial(
            DummyDataBase.setup,
            self.logger,
            self.loop
        )

        # Link UbloxReceiver attributes and methods to SerialReceiver.setup class method
        serial_setup = partial(
            FakeSerialReceiver.setup,
            self.logger,
            loop
        )

        # Setup database
        self.db = await database_setup()

        # Link parse message function to DataBase.store_data coroutine and to the event loop
        self.data_to_store = partial(parse_message, self.db.store_data, self.loop)

        # Setup serial connection
        self.serial = await serial_setup()

        # Setup made correctly, return self
        return self

    @classmethod
    def stop_test(cls):
        """
        Raise an exception to stop the test
        """
        raise Exception


