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
import asyncio
import signal
from datetime import datetime
from functools import partial
from concurrent.futures import ThreadPoolExecutor

# Asynchronous libraries
import uvloop
import asyncpg
from aiologger import Logger

# Typing
from typing import Optional, Union, Callable, Dict, Any

# Ublox constants and utilities
from ublox_reader.constants import*
from ublox_reader.utilities import parse_time_message, parse_message
# Ublox serial receiver
from ublox_reader.serial.receiver import SerialReceiver
from ublox_reader.serial.constants import UbloxSerialException


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
        # data_to_store method
        self.data_to_store = None  # type: Optional[Callable]

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
            ublox_reader = loop.run_until_complete(UbloxReceiver.set_up(loop))  # type: UbloxReceiver
        except (Exception, UbloxSerialException):
            loop.run_until_complete(UbloxReceiver.shut_down())
            loop.close()
            return

        # Add signals handler to close gracefully the receiver
        for s in signals:
            loop.add_signal_handler(
                s, lambda sig=s: asyncio.create_task(ublox_reader.close_all_connections()))

        # Set an exception handler to deal with the raised exceptions
        loop.set_exception_handler(ublox_reader.handle_exception)
        try:
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
        # type: (Union[uvloop.Loop, asyncio.AbstractEventLoop]) -> UbloxReceiver
        """
        Instantiate a UbloxReceiver instance and setup the serial receiver
        and the connection pool to the db

        :param loop:  Asynchronous event loop implementation provided by uvloop
        :return: A UbloxReceiver instance
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
            self.logger.info(f"{datetime.now()} : INFO : "
                             f"[DataBase]: created a connection pool to {DB_HOST}")

        except OSError as error:
            # Log the exception
            await self.logger.error(f"{datetime.now()} : UbloxReceiver: "
                                    f"[ConnectionError]: can't connect to the db {error.strerror}")
            raise Exception

        except asyncio.TimeoutError:
            # Log the exception
            await self.logger.error(f"{datetime.now()} : ERROR : "
                                    f"[DataBase]: can't connect to the db ")
            raise Exception

        except asyncpg.PostgresError as error:
            # Log the exception
            await self.logger.error(f"{datetime.now()} : UbloxReceiver: "
                                    f"[DataBaseError]: {str(error.as_dict())}")
            raise Exception

        # Link parse message function to the coroutine to self.store_data and to the event loop
        self.data_to_store = partial(parse_message, self.store_data, self.loop)

        # TODO: create a package for the db
        #  use functools partial to initialize it like the serial connection

        # Link UbloxReceiver attributes and methods to SerialReceiver.setup class method
        serial_setup = partial(
            SerialReceiver.setup,
            self.logger,
            loop
        )
        # Setup serial connection
        self.serial = await serial_setup()

        # Setup made correctly, return self
        return self

    async def get_data(self):
        # type: () -> None
        """
        Read data from serial connection until obtain a ublox message.
        Once a message is obtained, put it in the queue of the
        data to parse
        """
        while True:
            async for message in self.serial.ublox_message():
                # Put the message in a queue to parse it
                await self.data_to_parse.put(message)

    async def parse_data(self):
        # type: () -> None
        """
        Parse data received from the serial connection, the data that are
        useful are only Time messages and Galileo messages. In case of one
        of those messages, analyze them in an executor. Parse Galileo data only if
        a Time message was already received. Then schedule the storing of useful data in the database
        """
        while True:
            # Get data from the queue
            data = await self.data_to_parse.get()
            # This is a TIME message
            if data[0] == 1:
                # Set the received time message flag
                self.time_flag = True
                # Analyze the message in a executor
                asyncio.ensure_future(self.loop.run_in_executor(self.parse_data_executor, parse_time_message, data))

            # This is a GNSS message
            elif data[0] == 2 and self.time_flag:
                # Check if it's a GALILEO message
                # {GPS: 0}, {SBUS: 1}, {GALILEO: 2}, {BEIDU: 3}, {IMES: 4}, {QZSS: 5}, {GLONASS: 6}
                if data[4] == 2:
                    # Analyze the message in a executor and scheduling the storing of the data
                    asyncio.ensure_future(self.loop.run_in_executor(self.parse_data_executor, self.data_to_store, data))

            # set the parsing of the data done
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
                self.logger.warning(f"{datetime.now()} : WARNING : [DataBase]: "
                                    f"error inserting data to db")

        except asyncpg.PostgresWarning as warning:
            # Log the warning code
            self.logger.warning(f"{datetime.now()} : WARNING : [DataBase]: "
                                f"{str(warning.as_dict())}")

        except asyncpg.PostgresError as error:
            # Log the error code
            self.logger.error(f"{datetime.now()} : ERROR : [DataBase]: "
                              f"{str(error.as_dict())}")

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

    async def close_all_connections(self, msg=None):
        # type:(Optional[str]) -> None
        """
        Close gracefully all the connections

        :param msg = Message of the serious exception
        """
        # Check if there was an exception
        if msg:
            # Log the exception
            await self.logger.error(msg)

        # Log the closing of all the connections
        await self.logger.warning(f"{datetime.now()} : WARNING : [UbloxReceiver]: closing all connections")

        await self.shut_down()

        # Close serial connection
        await self.serial.stop_serial()

        try:
            # Close gracefully the connection pool
            await asyncio.wait_for(self.pool.close(), timeout=1)

        except asyncio.TimeoutError:
            # Timeout expired
            await self.logger.warning(f"{datetime.now()} : WARNING : [DataBase]: error closing the pool")

        # Shutdown parse data executor
        self.parse_data_executor.shutdown(wait=False)

        # Log the exit from the application
        await self.logger.info(f"{datetime.now()} : INFO : [UbloxReceiver]: shutdown completed")
        # Stop the loop
        self.loop.stop()

    @classmethod
    async def shut_down(cls):
        """
        Cancel all pending tasks
        """
        # Pending tasks
        pending = [t for t in asyncio.all_tasks() if t is not
                   asyncio.current_task()]

        # Cancel all pending tasks
        [task.cancel() for task in pending]

        # Wait for all pending tasks to be cancelled
        await asyncio.gather(*pending, return_exceptions=True)
