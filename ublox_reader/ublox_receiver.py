#!/usr/bin/env python3
"""
Asynchronous Ublox Receiver

:author: Angelo Cutaia
:copyright: Copyright 2020, Angelo Cutaia
:version: 0.0.1

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
from concurrent.futures import ThreadPoolExecutor

# Asynchronous libraries
import uvloop
import aioserial
import asyncpg
from aiologger import Logger

# Ublox constants and utilities
from ublox_reader.constants import*
from ublox_reader.utilities import parse_time_message, parse_message

# Typing
from typing import Optional, Union, List


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
    and the publish the information received from the serial connection
    to a PostgreSQL db
    """
    def __init__(self, loop):
        # type: (uvloop.Loop) -> None
        """
        Set up UbloxReader
        """
        # serial transmission
        self.serial = None  # type: Optional[aioserial.AioSerial]
        # logger
        self.logger = None  # type: Optional[Logger]
        # connection pool
        self.pool = None  # type: Optional[asyncpg.pool.Pool]
        # stop event
        self.reader_stop = asyncio.Event()  # type: asyncio.Event
        # executor to parse the data
        self.parse_data_executor = ThreadPoolExecutor(max_workers=1)  # type: ThreadPoolExecutor
        # event loop
        self.loop = loop  # type: uvloop.Loop
        # flag to notify the reception of a time message
        self.time_flag = False  # type: bool

    @classmethod
    def run(cls):
        """
        Setup a Ublox Receiver and starts to get the data. In
        case of a keyboard interrupt, stop the Reader and cleanup
        gracefully
        @return:
        """
        # Get the Event Loop
        loop = asyncio.get_event_loop()
        # Setup the Reader
        ublox_reader = loop.run_until_complete(UbloxReceiver.set_up(loop))  # type: UbloxReceiver
        try:
            # Get Data
            loop.run_until_complete(ublox_reader.get_data())
        except KeyboardInterrupt:
            # Cleanup
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
        @return  a UbloxReader Instance:
        """
        # Create an instance of UbloxReader
        self = UbloxReceiver(loop)
        # Instantiate logger
        self.logger = Logger.with_default_handlers(name="UbloxReceiver", loop=loop)
        try:
            # Open serial connection
            self.serial = aioserial.AioSerial(SERIAL_PORT, SERIAL_BAUDRATE, loop=loop)

            # SerialPort Log
            self.logger.info(time.ctime() + ": UbloxReceiver: [Connection]: Connected to " + SERIAL_PORT)
            self.logger.info(time.ctime() + ": UbloxReceiver: [SerialPort]: Sending setup bytes")

            # Set up serial communication
            for BYTES in SETUP_BYTES:
                await self.serial.write_async(BYTES)

            # Create a connection pool to the db
            self.pool = await asyncio.wait_for(
                asyncpg.create_pool(
                    loop=loop,
                    host=DB_HOST,
                    port=DB_PORT,
                    user=DB_USER,
                    password=DB_PW,
                    database=DB
                ), timeout=20
            )
            # Database Log
            self.logger.info(time.ctime() + ": UbloxReceiver: [Connection]: Created a connection pool to " + DB_HOST)

        except aioserial.SerialException as error:
            # Log the exception
            await self.logger.error(time.ctime() + ": UbloxReceiver: [SerialPortError]: " + error.strerror)
            # Set event to stop the reader
            self.reader_stop.set()

        except asyncio.TimeoutError:
            # Log the exception
            await self.logger.error(time.ctime() + ": UbloxReceiver: [ConnectionError]: Can't connect to the db ")
            # Close serial connection
            self.serial.close()
            # Set event to stop the reader
            self.reader_stop.set()

        except asyncpg.PostgresError as error:
            # Log the exception
            await self.logger.error(time.ctime() + ": UbloxReceiver: [DataBaseError]: " + str(error.as_dict()))
            # Close serial connection
            self.serial.close()
            # Set event to stop the reader
            self.reader_stop.set()
        finally:
            return self

    async def get_data(self) -> None:
        """
        Read data from serial connection until find the
        delimeter sequence of bytes and schedule the coroutine that
        will parse them.
        This coroutine will run until a reader_stop event is set
        @return:
        """
        while not self.reader_stop.is_set():
            try:
                # Read data
                data: bytes = await self.serial.read_until_async(DELIMETER)
                # Schedule the parsing of the data
                self.loop.create_task(self.parse_data(data))

            except aioserial.SerialException as error:
                # Log the error
                self.logger.error(time.ctime() + ": UbloxReceiver: [SerialPortError]: " + error.strerror)
                # Disconnect the reader
                await self.close_all_connections()

    async def parse_data(self, data: bytes) -> None:
        """
        Parse data received from the serial connection, the data that are
        useful are only Time messages and Galileo messages. In case of one
        of those messages, remove the last two bytes cause they are the delimeter
        bytes and analyze them in an executor. After that schedule the storing
        of all the Galileo message received af the first Time message
        @param data:bytes to parse
        @return:
        """
        # This is a TIME message
        if data[0] == 1:
            # Set the received time message flag
            self.time_flag = True
            # Analyze the message in a executor
            await self.loop.run_in_executor(self.parse_data_executor, parse_time_message, data[0:-2])

        # This is a GNSS message
        elif data[0] == 2 and self.time_flag:
            # Check if it's a GALILEO message
            # {GPS: 0}, {SBUS: 1}, {GALILEO: 2}, {BEIDU: 3}, {IMES: 4}, {QZSS: 5}, {GLONASS: 6}
            if data[4] == 2:
                # Analyze the message in a executor and obtain the data to store in the db
                data_to_store = await self.loop.run_in_executor(self.parse_data_executor, parse_message, data[0:-2])
                # Schedule the storing of the data
                self.loop.create_task(self.store_data(data_to_store))

    async def store_data(self, data_to_store: List[tuple]) -> None:
        """
        Use a connection from the pool to insert the data in the db
        and check if the insertion is successful then release the
        connection. If all the connection are busy, await for
        a connection to be free.
        @param data_to_store: values to insert in the db
        @return:
        """
        try:
            # Take a connection from the pool and execute the query
            status = await self.pool.execute(DB_QUERY, *data_to_store)
            # Check if there was an error storing the data
            if status != "INSERT 0 1":
                # Log the warning
                self.logger.warning(time.ctime() + ": UbloxReceiver: [DataBase]: [Warning]: Error inserting data to db")

        except asyncpg.PostgresWarning as warning:
            # Log the warning code
            self.logger.warning(time.ctime() + ": UbloxReceiver: [DataBase]: [Warning]: " + str(warning.as_dict()))

        except asyncpg.PostgresError as error:
            # Log the error code
            self.logger.error(time.ctime() + ": UbloxReceiver: [DataBase]: [Error]: " + str(error.as_dict()))

    async def close_all_connections(self) -> None:
        """
        Close gracefully all the connections
        @return:
        """
        # Log the closing of all the connections
        self.logger.info("\n" + time.ctime() + ": UbloxReceiver: [Connection]: Closing all connections")
        # Stop the Reader
        self.reader_stop.set()
        # Give time to finish pending coroutines
        await asyncio.sleep(1)
        # Close serial connection
        self.serial.close()
        try:
            # Close gracefully the connection pool
            await asyncio.wait_for(self.pool.close(), timeout=1)
        except asyncio.TimeoutError:
            # Timeout expired
            self.logger.warning(time.ctime() + ": UbloxReceiver: [Connection]: Error closing the pool")
        finally:
            # Log the exit from the application
            await self.logger.info(time.ctime() + ": UbloxReceiver: EXIT")
