#!/usr/bin/env python3
"""
Fake ublox_reader.serial.receiver.SerialReceiver

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
import os
import pty
import time
import threading
from logging import Logger
from typing import AsyncIterable, Union

# Asynchronous libraries
from uvloop import Loop

# SerialReceiver
from ublox_reader.serial.receiver import SerialReceiver
from ublox_reader.serial.constants import SETUP_BYTES, UbloxSerialException
from tests.constants import FAKE_DATA

# Open the pseudoterminal
master, slave = pty.openpty()

# ------------------------------------------------------------------------------


# Module version
__version_info__ = (1, 0, 0)
__version__ = ".".join(str(x) for x in __version_info__)

# Documentation strings format
__docformat__ = "restructuredtext en"


# ------------------------------------------------------------------------------


########################
# FAKE SERIAL RECEIVER #
########################


class FakeSerialReceiver:
    """
    A class that simulates the  serial connection and the
    behaviour of the SerialReceiver
    """

    # serial connection
    serial: SerialReceiver = None

    def __init__(self, simulate="all"):
        # type: (str) -> None
        """
        Setup a FakeSerialReceiver
        """
        # simulate
        self.simulate = simulate
        # stop event
        self.stop_event = threading.Event()
        # start the simulation of the receiver after timer
        self.start_simulation = threading.Timer(1, self.mock_device)
        # set the name
        self.start_simulation.setName("simulate_the_device")
        # start the timer
        self.start_simulation.start()

    @classmethod
    async def setup(cls, logger, loop, simulate="all", port=os.ttyname(slave)):
        # type: (Logger, Loop, str, Union[int, str]) -> FakeSerialReceiver
        """
        Instantiate a FakeSerialReceiver and simulate the serial connection
        and the hardware of the receiver

        :param logger: Asynchronous logger
        :param loop: Event loop
        :param simulate: simulate completely the hardware or only the setup
        :param port: Serial Port to simulate
        :return: A FakeSerialReceiver instance
        """
        # Create an instance of FakeSerialReceiver
        self = FakeSerialReceiver(simulate=simulate)

        try:
            # Setup
            self.serial = await SerialReceiver.setup(logger, loop, port)

        except UbloxSerialException:
            # Stop the simulation of the hardware
            self.start_simulation.cancel()
            # Re raise the exception
            raise UbloxSerialException

        # everything ok
        return self

    def mock_device(self, msg_per_second=20):
        # type: (int) -> None
        """
        Simulate the serial receiver hardware

        :param msg_per_second: Number of messages sent by the receiver in one second
        """
        # Check if the setup bytes are received well
        for i in range(len(SETUP_BYTES)):
            assert (
                os.read(master, len(SETUP_BYTES[i])) == SETUP_BYTES[i]
            ), "Bytes read should be equal to SETUP_BYTES"

        # Check if the simulation will be complete
        if self.simulate == "all":
            # Open the file, and send the message to the fake serial port
            with open(FAKE_DATA, "r") as fp:
                for line in fp:
                    # Check if the simulation has ben interrupted
                    if not self.stop_event.is_set():
                        os.write(master, bytearray.fromhex(line))
                        # sleep to have a correct number of messages send in one second
                        time.sleep(1 / msg_per_second)

    async def ublox_message(self) -> AsyncIterable[bytearray]:
        """
        Wraps SerialReceiver.ublox_message method
        """
        async for message in self.serial.ublox_message():
            yield message

    def close(self):
        """
        Wraps SerialReceiver.stop method
        """
        self.serial.close()

    async def stop_serial(self):
        """
        Wraps SerialReceiver.stop_serial method
        """
        await self.serial.stop_serial()
        # set stop event and await the thread to finish it's job
        self.stop_event.set()
        self.start_simulation.join()
