#!/usr/bin/env python3
"""
Tests the ublox_reader.serial package

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
import random
from typing import Union, List
# Test
import pytest

# Asynchronous Library
import uvloop
from aiologger import Logger

# SerialReceiver constants
from ublox_reader.serial.constants import UbloxSerialException

# FakeSerialReceiver
from tests.ublox_reader.serial.fake_serial import FakeSerialReceiver
from tests.constants import path_fake_data

# ------------------------------------------------------------------------------


# Module version
__version_info__ = (1, 0, 0)
__version__ = ".".join(str(x) for x in __version_info__)

# Documentation strings format
__docformat__ = "restructuredtext en"


# ------------------------------------------------------------------------------


@pytest.yield_fixture()
def event_loop():
    loop = uvloop.Loop()
    yield loop
    loop.close()


class TestSerial:
    """
    Test the receiver module
    """
    # instantiate in this way to fix the warning
    loop: Union[uvloop.Loop, asyncio.AbstractEventLoop] = None
    # add logger
    logger: Logger = None
    # message list
    message_list: List[Union[int, bytearray]] = None
    # random exception raised in a random iteration
    random_exception: int = None

    async def configure(self, with_message: bool = False, with_exception: bool = False):
        """
        Setup every test

        :param with_message: indicate if fake messages have to be stored
        :param with_exception: indicate if the receiver will raise an exception while parsing data
        """
        # Get the event loop
        self.loop = asyncio.get_running_loop()

        # Instantiate and disable the logger
        self.logger = Logger.with_default_handlers(name="test", loop=self.loop)
        self.logger.disabled = True

        # check if fake messages have to be stored
        if with_message:
            # store fake_data
            with open(path_fake_data, "r") as fp:
                self.message_list = [
                    # remove the first two bytes cause they are the delimeter
                    bytearray.fromhex(line)[2:]
                    for line in fp
                ]
            # check if an exception has to be risen
            if with_exception:
                # Generate an exception in a random iteration
                self.random_exception = random.randint(0, len(self.message_list) - 3)

    @pytest.mark.asyncio
    async def test_setup(self):
        """
        Test the setup of the SerialReceiver
        """
        # setup the test
        await self.configure()

        # check if the setup raise an exception
        with pytest.raises(UbloxSerialException):
            await FakeSerialReceiver.setup(self.logger, self.loop, simulate="setup", port="wrong")

        # Check if everything is ok
        receiver = await FakeSerialReceiver.setup(self.logger, self.loop, simulate="setup")

        # stop the fake receiver
        await receiver.stop_serial()

    @pytest.mark.asyncio
    async def test_ublox_message_with_no_exception(self):
        """
        Test ublox_message method without exceptions
        """
        # setup the test
        await self.configure(with_message=True)

        # instantiate the receiver
        receiver = await FakeSerialReceiver.setup(self.logger, self.loop)

        # try to get all data correctly
        for i in range(0, len(self.message_list)):
            # get_messages from the serial connection
            async for message in receiver.ublox_message():
                assert message == self.message_list[i], "Bytes should be equal"

        # cleanup
        await receiver.stop_serial()

    @pytest.mark.asyncio
    async def test_ublox_message_with_exception(self):
        """
        Test ublox_message method with exceptions
        """
        # setup test
        await self.configure(with_message=True, with_exception=True)

        # instantiate the receiver
        receiver = await FakeSerialReceiver.setup(self.logger, self.loop)

        # Check if the receiver raise the exception correctly
        with pytest.raises(UbloxSerialException):
            # try to get all data correctly
            for i in range(0, len(self.message_list)):
                # get messages from the serial connection
                async for message in receiver.ublox_message():
                    assert message == self.message_list[i], "Bytes should be equal"
                    # check if we have to raise an exception
                    if i == self.random_exception:
                        receiver.close()
        # cleanup
        await receiver.stop_serial()















