#!/usr/bin/env python3
"""
Asynchronous database for UbloxReader

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
from datetime import datetime

# Asynchronous libraries
import asyncpg
from aiologger import Logger
from uvloop import Loop

# constants
from ublox_reader.database.constants import DB_HOST, DB_PORT, DB_USER, DB_PWD, DB, DataBaseException

# ------------------------------------------------------------------------------


# Module version
__version_info__ = (1, 0, 0)
__version__ = ".".join(str(x) for x in __version_info__)

# Documentation strings format
__docformat__ = "restructuredtext en"


# ------------------------------------------------------------------------------


############
# DATABASE #
############


class DataBase:
    """
    A class that handles a postgresql database connection pool.
    The scope of this class is to build the database and save data inside it
    using a connection pool
    """
    # connection pool
    pool: asyncpg.pool.Pool = None

    def __init__(self, logger, loop, host, port, user, password, database):
        # type: ( Logger, Loop, str, int, str, str, str) -> None
        """
        Setup Database

        :param logger: Asynchronous logger
        :param loop: Event Loop
        :param host: Database host address
        :param port: Port number to connect to at the server host
        :param user: User of the database
        :param password: Password of the database
        :param database: Database name
        """
        # Logging
        self.logger = logger
        # Event loop
        self.loop = loop
        # Database constants
        self.host = host
        self.port = port
        self.user = user
        self.password = password
        self.database = database
        # Pool constants
        self.pool_min_size = 1
        self.pool_max_size = 10
        self.inactive_connection_lifetime = 60
        # timeout
        self.timeout = 20

    @classmethod
    async def setup(
            cls,
            logger,
            loop,
            host=DB_HOST,
            port=DB_PORT,
            user=DB_USER,
            password=DB_PWD,
            database=DB
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
        # instantiate
        self = DataBase(logger, loop, host, port, user, password, database)

        try:
            # create the database
            await self.create_database_if_not_exist()

        except OSError as error:
            # Log the exception
            await self.logger.error(f"{datetime.now()} : ERROR : "
                                    f"[DataBase]: can't connect to the db {error.strerror}")

            # raise exception to sto the execution
            raise DataBaseException

        except asyncpg.PostgresError as error:
            # Log the exception
            await self.logger.error(f"{datetime.now()} : ERROR : "
                                    f"[DataBase]: {str(error.as_dict())}")

            # raise exception to sto the execution
            raise DataBaseException

        # Setup made correctly, return self
        return self

    async def create_database_if_not_exist(self):
        """
        Create a connection pool to the db.
        If the db doesn't exist, create it and assign to
        the specified user
        """
        try:
            # create a connection pool
            self.pool = await asyncio.wait_for(
                asyncpg.create_pool(
                    min_size=self.pool_min_size,
                    max_size=self.pool_max_size,
                    max_inactive_connection_lifetime=self.inactive_connection_lifetime,
                    loop=self.loop,
                    host=self.host,
                    port=self.port,
                    user=self.user,
                    password=self.password,
                    database=self.database
                ),
                timeout=self.timeout
            )
            # Database Log
            await self.logger.info(f"{datetime.now()} : INFO : "
                                   f"[DataBase]: created a connection pool to {self.host}")

        except asyncio.TimeoutError:
            # log the error
            await self.logger.error(f"{datetime.now()} : ERROR : "
                                    f"[DataBase]: timeout reached, can't connect to the database")
            # raise exception to stop the execution
            raise DataBaseException

        except asyncpg.InvalidCatalogNameError:
            # Database does not exist, create it
            await self.logger.warning(f"{datetime.now()} : WARNING : "
                                f"[DataBase]: database {self.database} doesn't exist")

            # create a single connection to the default user and the database template
            sys_conn = await asyncpg.connect(
                host=self.host,
                user=self.user,
                port=self.port,
                password=self.password,
                database="template1",
            )
            # create the database
            await sys_conn.execute(
                f'CREATE DATABASE "{self.database}" OWNER "{self.user}";'
            )
            # close the connection
            await sys_conn.close()
            # Database Log
            await self.logger.info(f"{datetime.now()} : INFO : "
                                   f"[DataBase]: created database {self.database}")

            # Connect to the newly created database.
            await self.create_database_if_not_exist()

    async def store_data(self, table, data_to_store):
        # type:(str, tuple) -> None
        """
        Use a connection from the pool to insert the data in the db
        and check if the insertion is successful then release the
        connection. If the table in which the data must be stored doesn't
        exist, it will create it. In case all the connections in the pool are busy,
        await for a connection to be free.

        :param table: Database table
        :param data_to_store:
        :return:
        """
        try:
            # Take a connection from the pool and execute the query
            await self.pool.execute(
                '''
                INSERT INTO {} (
                receptiontime,
                timestampmessage_unix,
                raw_galtow,
                raw_galwno,
                raw_leaps,
                raw_data,
                raw_authbit,
                raw_svid,
                raw_numwords,
                raw_ck_b,
                raw_ck_a,
                raw_ck_a_time,
                raw_ck_b_time,
                timestampmessage_galileo
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14);'''.format(table),
                *data_to_store
            )

        # Check if the table does'nt exist
        except asyncpg.UndefinedTableError:
            # Log the error code
            await self.logger.warning(f"{datetime.now()} : WARNING : [DataBase]: "
                                      f"relation {table} doesn't exist")
            # Create the table
            await self.pool.execute(
                '''
                    CREATE TABLE {} (
                    receptiontime bigint,
                    timestampmessage_unix bigint,
                    PRIMARY KEY (timestampmessage_unix),
                    raw_galtow integer,
                    raw_galwno integer,
                    raw_leaps integer,
                    raw_data text,
                    raw_authbit integer,
                    raw_svid integer,
                    raw_numwords integer,
                    raw_ck_b integer,
                    raw_ck_a integer,
                    raw_ck_a_time integer,
                    raw_ck_b_time integer,
                    timestampmessage_galileo bigint
                    );
                    '''.format(table)
            )
            # Log
            await self.logger.info(f"{datetime.now()} : INFO : [DataBase]: relation {table} created")

            # Create a index for the table
            await self.pool.execute(
                "CREATE INDEX CONCURRENTLY idx_timestampmessage_unix on {} "
                "(timestampmessage_unix DESC NULLS LAST);".format(table)
            )

            # store data in the new table
            await self.store_data(table, data_to_store)

    async def close(self):
        """
        Close all the connections to the Database
        """
        try:
            # Close gracefully the connection pool
            await asyncio.wait_for(self.pool.close(), timeout=1)

        except asyncio.TimeoutError:
            # Timeout expired
            await self.logger.warning(f"{datetime.now()} : WARN : [DataBase]: error closing the pool")

        finally:
            # Log
            await self.logger.info(f"{datetime.now()} : INFO : [DataBase]: disconnected from {self.host}")
