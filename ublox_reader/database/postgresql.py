#!/usr/bin/env python3
"""
Asynchronous database for UbloxReader

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

# Asynchronous libraries
import asyncpg
from uvloop import Loop

# constants
from .constants import DB_HOST, DB_PORT, DB_USER, DB_PWD, DB, DataBaseException

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

    def __init__(
        self,
        logger: Logger,
        loop: Loop,
        host: str,
        port: int,
        user: str,
        password: str,
        database: str,
    ) -> None:
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
        database=DB,
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
            self.logger.error(f"can't connect to the db {error.strerror}")

            # raise exception to sto the execution
            raise DataBaseException

        except asyncpg.PostgresError as error:
            # Log the exception
            self.logger.error(f"{str(error.as_dict())}")

            # raise exception to sto the execution
            raise DataBaseException

        # Setup made correctly, return self
        return self

    async def create_database_if_not_exist(self) -> None:
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
                    database=self.database,
                ),
                timeout=self.timeout,
            )
            # Database Log
            self.logger.info(f"created a connection pool to {self.host}")

        except asyncio.TimeoutError:
            # log the error
            self.logger.error("timeout reached, can't connect to the database")
            # raise exception to stop the execution
            raise DataBaseException

        except asyncpg.InvalidCatalogNameError:
            # Database does not exist, create it
            self.logger.warning(f"database {self.database} doesn't exist")

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
            self.logger.info(f"created database {self.database}")

            # Connect to the newly created database.
            await self.create_database_if_not_exist()

    async def store_data(self, table: str, data_to_store: tuple) -> None:
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
                f"""
                INSERT INTO "{table}" (
                receptiontime,
                timestampmessage_unix,
                raw_galtow,
                raw_galwno,
                raw_leaps,
                raw_data,
                galileo_data,
                raw_authbit,
                raw_svid,
                raw_numwords,
                raw_ck_b,
                raw_ck_a,
                raw_ck_a_time,
                raw_ck_b_time,
                osnma,
                timestampmessage_galileo
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16);""",
                *data_to_store,
            )

        # Check if the table does'nt exist
        except asyncpg.UndefinedTableError:
            # Log the error code
            self.logger.warning(f"relation {table} doesn't exist")

            # Create the table
            async with self.pool.acquire() as con:
                await con.execute(
                    f"""
                        CREATE TABLE IF NOT EXISTS "{table}" (
                        receptiontime bigint,
                        timestampmessage_unix bigint,
                        PRIMARY KEY (timestampmessage_unix),
                        raw_galtow integer,
                        raw_galwno integer,
                        raw_leaps integer,
                        raw_data text,
                        galileo_data text,
                        raw_authbit bigint,
                        raw_svid integer,
                        raw_numwords integer,
                        raw_ck_b integer,
                        raw_ck_a integer,
                        raw_ck_a_time integer,
                        raw_ck_b_time integer,
                        osnma integer,
                        timestampmessage_galileo bigint
                        );
                         """
                )
                # Log
                self.logger.info(f"relation {table} created")

                # Create a index for the table
                await con.execute(
                    f"""CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_timestampmessage_unix on "{table}"
                     (timestampmessage_unix DESC NULLS LAST);"""
                )

            # store data in the new table
            await self.store_data(table, data_to_store)

    async def close(self) -> None:
        """
        Close all the connections to the Database
        """
        try:
            # Close gracefully the connection pool
            await asyncio.wait_for(self.pool.close(), timeout=1)

        except asyncio.TimeoutError:
            # Timeout expired
            self.logger.warning("error closing the pool")

        finally:
            # Log
            self.logger.info(f"disconnected from {self.host}")
