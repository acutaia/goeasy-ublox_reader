#!/usr/bin/env python3
"""
Asynchronous Ublox Receiver

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
import asyncio
from functools import partial
from concurrent.futures import ThreadPoolExecutor

# Asynchronous libraries
import uvloop
import asyncpg
from aiologger import Logger

# Typing
from typing import Optional, Union

# Ublox constants and utilities
from ublox_reader.constants import*
from ublox_reader.utilities import parse_time_message, parse_message
# Ublox serial receiver
from ublox_reader.serial.receiver import SerialReceiver


# Substitute asyncio loop with uvloop
asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())

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
    def __init__(self, loop):
        # type: (uvloop.Loop) -> None
        """
        Set up UbloxReader

        :param loop: Asynchronous event loop implementation provided by uvloop
        """
        # serial transmission
        self.serial = None  # type: Optional[SerialReceiver]
        # logger
        self.logger = None  # type: Optional[Logger]
        # connection pool
        self.pool = None  # type: Optional[asyncpg.pool.Pool]
        # stop event
        self.receiver_stop = asyncio.Event()  # type: asyncio.Event
        # executor to parse the data
        self.parse_data_executor = ThreadPoolExecutor(max_workers=1)  # type: ThreadPoolExecutor
        # event loop
        self.loop = loop  # type: uvloop.Loop
        # flag to notify the reception of a time message
        self.time_flag = False  # type: bool
        # queue containing the data to parse
        self.data_to_parse = asyncio.Queue()  # type: asyncio.Queue

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

        # Setup the Reader
        ublox_reader = loop.run_until_complete(UbloxReceiver.set_up(loop))  # type: UbloxReceiver

        # Check if something went wrong during the setup
        if not ublox_reader:
            # Stop and close the Event Loop
            loop.stop()
            loop.close()
            return

        # Schedule get_data
        get_data = loop.create_task(ublox_reader.get_data())

        # Schedule parse data
        parse_data = loop.create_task(ublox_reader.parse_data())

        try:
            # Get data, parse and store until a keyboard interrupt
            loop.run_until_complete(
                asyncio.wait({get_data, parse_data})
            )
        except KeyboardInterrupt:
            # Disconnect
            loop.run_until_complete(ublox_reader.close_all_connections())

        finally:
            # Close the Event Loop
            loop.close()

    @classmethod
    async def set_up(cls, loop):
        # type: (Union[uvloop.Loop, asyncio.AbstractEventLoop]) -> UbloxReceiver
        """
        Instantiate a UbloxReceiver instance and setup the serial receiver
        and the connection pool to the db

        :param loop:  Asynchronous event loop implementation provided by uvloop
        :return: A UbloxReceiver instance, if no exceptions during the setup
                of the database and of the SerialReceiver, else return None
        """
        # Create an instance of UbloxReader
        self = UbloxReceiver(loop)
        # Instantiate logger
        self.logger = Logger.with_default_handlers(name="UbloxReceiver", loop=loop)

        try:
            # Create a connection pool to the db
            self.pool = await asyncio.wait_for(
                asyncpg.create_pool(
                    min_size=1,
                    max_size=10,
                    loop=loop,
                    host=DB_HOST,
                    port=DB_PORT,
                    user=DB_USER,
                    password=DB_PW,
                    database=DB,
                ), timeout=20
            )
            # Database Log
            self.logger.info("".join(
                [time.ctime(), ": UbloxReceiver: [Connection]: created a connection pool to ", DB_HOST])
            )

        except OSError as error:
            # Log the exception
            await self.logger.error("".join(
                [time.ctime(), ": UbloxReceiver: [ConnectionError]: can't connect to the db ", error.strerror])
            )
            # Set flag to stop the reader
            self.receiver_stop.set()

        except asyncio.TimeoutError:
            # Log the exception
            await self.logger.error("".join(
                [time.ctime(), ": UbloxReceiver: [ConnectionError]: can't connect to the db "])
            )

            # Set flag to stop the reader
            self.receiver_stop.set()

        except asyncpg.PostgresError as error:
            # Log the exception
            await self.logger.error("".join(
                [time.ctime(), ": UbloxReceiver: [DataBaseError]: ", str(error.as_dict())])
            )

            # Set event to stop the reader
            self.receiver_stop.set()

        # Check if the instantiation of the pool was successful
        if self.pool:

            # TODO: create a package for the db
            #  use functools partial to initialize it like the serial connection

            # Link UbloxReceiver attributes and methods to SerialReceiver.setup class method
            serial_setup = partial(
                SerialReceiver.setup,
                self.logger,
                self.receiver_stop,
                self.close_all_connections,
                loop
            )
            # Setup serial connection
            self.serial = await serial_setup()
            # Check if the instantiation and the setup of the serial connection was successful
            if self.serial:
                return self

        # Something went wrong
        return None

    async def get_data(self):
        # type: () -> None
        """
        Read data from serial connection until obtain a ublox message.
        Once a message is obtained, put it in the queue of the
        data to parse
        """
        async for message in self.serial.ublox_message():
            # Put the message in a queue to parse it
            self.data_to_parse.put_nowait(message)

    async def parse_data(self):
        # type: () -> None
        """
        Parse data received from the serial connection, the data that are
        useful are only Time messages and Galileo messages. In case of one
        of those messages, analyze them in an executor. Parse Galileo data only if
        a Time message was already received.
        Then schedule the storing of useful data in the database
        """
        while not self.receiver_stop.is_set():
            # Get data from the queue
            data = await self.data_to_parse.get()
            # This is a TIME message
            if data[0] == 1:
                # Set the received time message flag
                self.time_flag = True
                # Analyze the message in a executor
                await self.loop.run_in_executor(self.parse_data_executor, parse_time_message, data)

            # This is a GNSS message
            elif data[0] == 2 and self.time_flag:
                # Check if it's a GALILEO message
                # {GPS: 0}, {SBUS: 1}, {GALILEO: 2}, {BEIDU: 3}, {IMES: 4}, {QZSS: 5}, {GLONASS: 6}
                if data[4] == 2:
                    # Analyze the message in a executor and obtain the data to store in the db
                    data_to_store = await self.loop.run_in_executor(self.parse_data_executor, parse_message, data)
                    # Put the data_to_store in a queue
                    self.loop.create_task(self.store_data(data_to_store))

            # set data
            self.data_to_parse.task_done()

    async def store_data(self, data_to_store):
        # type:(tuple) -> None
        """
        Use a connection from the pool to insert the data in the db
        and check if the insertion is successful then release the
        connection. If all the connection are busy, await for
        a connection to be free.

        :param data_to_store: Data to insert in the database
        """
        try:
            # Take a connection from the pool and execute the query
            status = await self.pool.execute(DB_QUERY, *data_to_store)
            # Check if there was an error storing the data
            if status != "INSERT 0 1":
                # Log the warning
                self.logger.warning("".join(
                    [time.ctime(), ": UbloxReceiver: [DataBase]: [Warning]: error inserting data to db"])
                )

        except asyncpg.PostgresWarning as warning:
            # Log the warning code
            self.logger.warning("".join(
                [time.ctime(), ": UbloxReceiver: [DataBase]: [Warning]: ", str(warning.as_dict())])
            )

        except asyncpg.PostgresError as error:
            # Log the error code
            self.logger.error("".join(
                [time.ctime(), ": UbloxReceiver: [DataBase]: [Error]: ", str(error.as_dict())])
            )

    async def close_all_connections(self):
        # type:() -> None
        """
        Close gracefully all the connections
        """
        # Log the closing of all the connections
        self.logger.info("".join(
            [time.ctime(), ": UbloxReceiver: [Connection]: closing all connections"])
        )

        # Stop the Reader
        self.receiver_stop.set()
        # Give time to finish pending coroutines
        await asyncio.sleep(3)
        # Close serial connection
        self.serial.close()

        try:
            # Close gracefully the connection pool
            await asyncio.wait_for(self.pool.close(), timeout=1)

        except asyncio.TimeoutError:
            # Timeout expired
            self.logger.warning("".join(
                [time.ctime(), ": UbloxReceiver: [Connection]: error closing the pool"])
            )

        finally:
            # Log the exit from the application
            await self.logger.info("".join(
                [time.ctime(), ": UbloxReceiver: [EXIT]"])
            )
