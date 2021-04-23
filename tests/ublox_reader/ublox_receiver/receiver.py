#!/usr/bin/env python3
"""
Dummy UbloxReceiver class for testing

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
from concurrent.futures import ThreadPoolExecutor
from collections import defaultdict
from logging import Logger
import signal
from typing import Union

# Asynchronous libraries
from uvloop import Loop

# Ublox
from ublox_reader.ublox_receiver import UbloxReceiver, UbloxLogger
from tests.ublox_reader.serial.fake_serial import FakeSerialReceiver
from tests.ublox_reader.database.dummy import DummyDataBase

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

    # Database
    db: DummyDataBase = None
    # Logger
    logger: Logger = UbloxLogger.get_logger("UbloxReceiver")
    # Serial
    serial: FakeSerialReceiver = None

    @staticmethod
    def run() -> None:
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
            ublox_reader: DummyUblox = loop.run_until_complete(DummyUblox.set_up(loop))
            ublox_reader.parser.validation_active = True
            ublox_reader.parser.executor = ThreadPoolExecutor(max_workers=3)
            ublox_reader.parser.file_path = "convolved_data.txt"
            ublox_reader.parser.valid_data_to_store = defaultdict(list)

        except (DataBaseException, UbloxSerialException):
            # Something went wrong
            loop.run_until_complete(DummyUblox.shut_down())
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
            # Schedule the stop of the execution
            loop.call_later(1, ublox_reader.stop_test)
            # Schedule get_data and parse data
            loop.create_task(ublox_reader.get_data())

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

        # disable for testing purpose
        self.logger.disabled = True

        # Setup database
        self.db = await DummyDataBase.setup(self.logger, loop)

        # Setup serial connection
        self.serial = await FakeSerialReceiver.setup(self.logger, loop)

        # Setup made correctly, return self
        return self

    def stop_test(self):
        """
        Trampoline function to check if the fake
        serial receiver is still sending data to the fake serial connection.
        When the fake data are ended, it will raise an exception to stop the execution
        """
        if self.serial.start_simulation.is_alive():
            self.loop.call_later(1, self.stop_test)
        else:
            raise Exception
