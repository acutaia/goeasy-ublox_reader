#!/usr/bin/env python3
"""
Fake ublox_reader.serial.receiver.SerialReceiver

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
import os
import pty
import time
import threading
from typing import Optional


# Asynchronous libraries
from aiologger import Logger
from uvloop import Loop


# SerialReceiver
from ublox_reader.serial.receiver import SerialReceiver
from ublox_reader.serial.constants import SETUP_BYTES


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


class FakeSerialReceiver(SerialReceiver):
    """
    A class that simulates the  serial connection and the
    behaviour of the SerialReceiver
    """
    def __init__(self, logger, loop, port=os.ttyname(slave)):
        # type: (Logger, Loop, Optional[int]) -> None
        """
        Setup a FakeSerialReceiver

        :param logger: Asynchronous logger
        :param loop: Event loop
        :param port: Serial port simulated thanks to the pseudo terminal
        """
        super().__init__(logger, loop, port=port)
        # start the simulation of the receiver after timer
        self.start_simulation = threading.Timer(0.3, self.mock_device)
        # set the name
        self.start_simulation.setName("simulate_the_device")
        # start the timer
        self.start_simulation.start()

    @staticmethod
    def mock_device(msg_per_second=5):
        # type: (int) -> None
        """
        Simulate the serial receiver hardware

        :param msg_per_second: Number of messages sent by the receiver in one second
        """
        # Check if the setup bytes are received well
        for i in range(len(SETUP_BYTES)):
            assert os.read(master, len(SETUP_BYTES[i])) == SETUP_BYTES[i], "Bytes read should be equal to SETUP_BYTES"

        # path to the file containing fake data
        path = os.path.join(os.path.abspath(os.path.dirname(__file__)), '..', 'fake_data.txt')

        # Open the file, and send the message to the fake serial port
        with open(path, "r") as fp:
            for line in fp:
                os.write(master, bytearray.fromhex(line))
                # sleep to have a correct number of messages send in one second
                time.sleep(1/msg_per_second)

    async def stop_serial(self):
        """
        Method to stop the FakeSerialReceiver
        """
        await super().stop_serial()
        self.start_simulation.join()


class Dummy(FakeSerialReceiver):
    """
    Dummy class that won't complete the setup
    method
    """
    def __init__(self, logger, loop, port="dummy/fake"):
        # type: (Logger, Loop, Optional[int]) -> None
        """
        Method that will always fail

        :param logger: Asynchronous logger
        :param loop: Event loop
        :param port: Serial port simulated thanks to the pseudo terminal
        """
        super().__init__(logger, loop, port=port)


