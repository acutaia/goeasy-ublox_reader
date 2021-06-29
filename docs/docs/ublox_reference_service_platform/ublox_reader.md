It is a Python-based software developed by exploiting the async paradigm. During boot, it configures the U-Blox
receiver to filter Galileo navigation messages and oversees the serial port connected to it. It is also in charge
of setting up the local PostgreSQL database, the tables and to dynamically fill in the entries with the data
received. The evolution of the application led to some changes on the data modelling of the reference
database. By considering that each reference system will be constantly gathering Galileo data for later usage,
even by exploiting indexes features, when databases entries grow over certain thresholds, query results were
given with unacceptable delays. Consequently, the design process led to the definition of the following
structures to prevent tables to grow excessively with respect to the necessary performances required by the
system. Galileo Navigation messages are stored in specific auto generated tables, with a standardized naming,
with respect to the satellite source and the reception year. The quoted structure enables higher parallelization
of requests and improved scalability in relation to the previous version. Each one of the messages, after being
parsed, is asynchronously given to the Position alteration detection library enabling the possibility to apply the
OS-NMA algorithm. The results of such process will then update the authenticity field of the navigation
message persistently stored by the reference system.
