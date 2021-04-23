#!/usr/bin/env python3
"""
Tests the ublox_reader.database package

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
from logging import Logger
from typing import Union

# Test
import pytest

# Asynchronous library
import uvloop

# DummyDataBase
from tests.constants import DATA_TO_STORE
from tests.ublox_reader.database.dummy import DummyDataBase
from ublox_reader.database.constants import DataBaseException
from ublox_reader.utilities import UbloxLogger

# ------------------------------------------------------------------------------


# Module version
__version_info__ = (1, 0, 0)
__version__ = ".".join(str(x) for x in __version_info__)

# Documentation strings format
__docformat__ = "restructuredtext en"


# ------------------------------------------------------------------------------


@pytest.fixture()
def event_loop():
    """
    Set uvloop as the default event loop
    """
    loop = uvloop.Loop()
    yield loop
    loop.close()


class TestDataBase:
    """
    Test the postgresql module
    """

    # instantiate in this way to fix the warning
    loop: Union[uvloop.Loop, asyncio.AbstractEventLoop] = None
    # add logger
    logger: Logger = UbloxLogger.get_logger("test")

    async def configure(self):
        """
        Setup every test
        """
        # Get the event loop
        self.loop = asyncio.get_running_loop()

        # Disable the logger
        self.logger.disabled = True

    @pytest.mark.asyncio
    async def test_setup(self):
        """
        Test the setup of the DataBase
        """
        # Setup the test
        await self.configure()

        # Check if the setup raise an exception

        with pytest.raises(DataBaseException):
            # Wrong host
            await DummyDataBase.setup(self.logger, self.loop, host="192.168.1.1")

        with pytest.raises(DataBaseException):
            # Wrong port
            await DummyDataBase.setup(self.logger, self.loop, port=8080)

        with pytest.raises(DataBaseException):
            # Wrong user
            await DummyDataBase.setup(self.logger, self.loop, user="wrong")

        #    with pytest.raises(DataBaseException):
        # Wrong password
        #        await DummyDataBase.setup(self.logger, self.loop, password="wrong")

        # Check if everything is ok
        database = await DummyDataBase.setup(self.logger, self.loop)

        # Close
        await database.close()

    @pytest.mark.asyncio
    async def test_store_data(self):
        """
        Test store data method
        """
        # Setup the test
        await self.configure()
        database = await DummyDataBase.setup(self.logger, self.loop)

        # Store data
        await database.store_data("test_table", DATA_TO_STORE)
        await database.close()
