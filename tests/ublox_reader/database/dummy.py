#!/usr/bin/env python3
"""
Dummy DataBase class useful for testing

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
# Standard Library
from logging import Logger

# Asynchronous libraries
import asyncpg
from uvloop import Loop

# DataBase
from ublox_reader.database.postgresql import DataBase

# ------------------------------------------------------------------------------


# Module version
__version_info__ = (1, 0, 0)
__version__ = ".".join(str(x) for x in __version_info__)

# Documentation strings format
__docformat__ = "restructuredtext en"


# ------------------------------------------------------------------------------


##################
# DUMMY DATABASE #
##################


class DummyDataBase(DataBase):
    """
    A class that simulates the behaviour of
    the DataBase
    """
    @ classmethod
    async def setup(
            cls,
            logger,
            loop,
            host="localhost",
            port=5432,
            user="postgres",
            password="postgres",
            database="test_database"
    ):  # type: (Logger, Loop, str, int, str, str, str) -> DataBase
        """
        Create a database and setup a connection pool

        :param logger: Asynchronous logger
        :param loop: Event Loop
        :param host: Database host address
        :param port: Port number to connect to at the server host
        :param user: User of the database
        :param password: Password of the database
        :param database: Database name
        :return: A DataBase instance
        """
        # Instantiate
        self = DummyDataBase(logger, loop, host, port, user, password, database)

        # Call the setup method of the parent class
        base: DataBase = await super().setup(
            logger,
            loop,
            host=host,
            port=port,
            user=user,
            password=password,
            database=database
        )

        # Assign the pool
        self.pool = base.pool

        return self

    async def destroy_database(self):
        """
        Destroy the database
        """
        sys_conn = await asyncpg.connect(
            host=self.host,
            user=self.user,
            port=self.port,
            password=self.password,
            database="template1",
        )
        # delete the database
        await sys_conn.execute(
            f'DROP DATABASE {self.database};'
        )
        # close the connection
        await sys_conn.close()

    async def close(self):
        """
        Close all the connections and destroy the database
        """
        await super().close()
        await self.destroy_database()
