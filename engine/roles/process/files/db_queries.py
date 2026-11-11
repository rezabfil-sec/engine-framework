import sqlite3
from sqlite3 import Error
import sys

import pandas as pd

# These are only debug flags to make it faster
offset = 10
limit = 10

# Since experiment is used for creating a table, we have to sanitize and it should have - in the name
# might need extension for other parts
def sanitize_exp_name(exp_name):
    return str(exp_name).replace("-","_")

def query_delay(processing_descriptor, group_nr):
    # Query for delay from the DB
    # Delays - assume presence of all relevant delays in the same table
    # E.g., group_id_1
    # Various scenarios
    # Scenario 1 - simple 1 source, 1 sink
    # Substract Tx_sink - Tx_source, correlate based on sequence number
    # Scenario 2 - 1 source, multiple sinks
    # Substract Tx_sink1, ..., Tx_sink2 - Tx_source, correlate based on sequence number
    # Scenario 1
    # Logic
    # c = conn.cursor()
    exp_name = sanitize_exp_name(processing_descriptor.experiment)
    table_name = 'group_id_' + str(group_nr) + "_" + exp_name
    conn = sqlite3.connect(processing_descriptor.db_path, timeout=50)
    print('connected to sqlite')
    sqlite_query = """SELECT DISTINCT sequence_number,
                timestamp_1,
                timestamp_2,
                delay,
                delay - lag(delay, 1) OVER () AS jitter
    FROM (
    SELECT t1.sequence_number,
           t1.timestamp_ns AS timestamp_1,
           t2.timestamp_ns AS timestamp_2,
           CASE
               WHEN (t2.timestamp_ns - t1.timestamp_ns) > 37000000000 THEN (t2.timestamp_ns - t1.timestamp_ns - 37000000000)
               WHEN (t2.timestamp_ns - t1.timestamp_ns) < 0 THEN (t2.timestamp_ns - t1.timestamp_ns + 37000000000)
               ELSE (t2.timestamp_ns - t1.timestamp_ns)
           END AS delay
    FROM {} AS t1
    JOIN {} AS t2
    ON t1.sequence_number = t2.sequence_number
    WHERE t1.role = 'source'
    AND t2.role = 'sink'
    ) AS subquery
    LIMIT {} OFFSET {};
    """.format(table_name, table_name, -limit, offset)
    delay_jitter = pd.read_sql_query(sqlite_query, conn)
    print(delay_jitter.head())
    return delay_jitter

def query_delay_jitter(processing_descriptor, group_nr, experiment, column):
    # Query for delay from the DB
    # Delays - assume presence of all relevant delays in the same table
    # E.g., group_id_1
    # Various scenarios
    # Scenario 1 - simple 1 source, 1 sink
    # Substract Tx_sink - Tx_source, correlate based on sequence number
    # Scenario 2 - 1 source, multiple sinks
    # Substract Tx_sink1, ..., Tx_sink2 - Tx_source, correlate based on sequence number
    # Scenario 1
    # Logic
    # c = conn.cursor()
    # FIXME for multiple experiments
    exp_name = sanitize_exp_name(experiment)
    table_name = 'delay_jitter_' + str(group_nr) + "_" + exp_name
    conn = sqlite3.connect(processing_descriptor.db_path, timeout=50)
    print('connected to sqlite')
    sqlite_query = """SELECT timestamp_1,
                {}
                FROM {};
    """.format(column, table_name)
    delay_jitter = pd.read_sql_query(sqlite_query, conn)
    print(table_name, delay_jitter.head())
    return delay_jitter

def query_loss(processing_descriptor, group_nr, experiment):
    # Query for delay from the DB
    # Delays - assume presence of all relevant delays in the same table
    # E.g., group_id_1
    # Various scenarios
    # Scenario 1 - simple 1 source, 1 sink
    # Substract Tx_sink - Tx_source, correlate based on sequence number
    # Scenario 2 - 1 source, multiple sinks
    # Substract Tx_sink1, ..., Tx_sink2 - Tx_source, correlate based on sequence number
    # Scenario 1
    # Logic
    # c = conn.cursor()
    exp_name = sanitize_exp_name(experiment)
    table_name = 'group_id_' + str(group_nr) + "_" + exp_name
    conn = sqlite3.connect(processing_descriptor.db_path, timeout=50)
    print('connected to sqlite')

    sqlite_query = """SELECT t1.sequence_number AS sequence_number,
        t1.timestamp_ns AS timestamp_source
        FROM {} AS t1
        LEFT JOIN {} AS t2
        ON t1.sequence_number = t2.sequence_number AND t2.role = 'sink'
        GROUP BY t1.sequence_number
        HAVING COUNT(*) = 1
        AND t1.role = 'source';
    """.format(table_name, table_name)
    packet_loss = pd.read_sql_query(sqlite_query, conn)
    print(packet_loss.head())
    return packet_loss

# DB usage functions
def create_connection(db_file):
    """ create a database connection to a SQLite database """
    conn = None
    try:
        conn = sqlite3.connect(db_file, timeout=50)
        print(sqlite3.version)
        return conn
    except Error as e:
        print(e)
    finally:
        if conn:
            conn.close()

def create_group_table(db_conn, group_nr, experiment):
    c = db_conn.cursor()
    exp_name = sanitize_exp_name(experiment)
    # Not for production new to possible wrong data format
    # Works for us
    # https://stackoverflow.com/questions/3247183/variable-table-name-in-sqlite
    database_cmd = '''CREATE TABLE IF NOT EXISTS {}([sequence_number] TEXT, [timestamp_ns] INTEGER, [node] TEXT, [role] TEXT, [misc] TEXT )'''.format('group_id_' + str(group_nr) + "_" + str(exp_name))
    print(database_cmd)
    c.execute(database_cmd)
    # Commit dbs
    db_conn.commit()    

def store_in_database(db_path, df, name, if_exists='append'):
    conn = sqlite3.connect(db_path, timeout=50)
    exp_name = sanitize_exp_name(name)
    # c = conn.cursor()
    # name = 'group_id_' + str(groupNr) + "_" + str(exp_name)
    # consider here if_exists should be append or replace
    # https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.to_sql.html
    # Scenario when more and more data are being appended to the table is not good (noise)
    df.to_sql(name=exp_name, con=conn, index=False, if_exists=if_exists)
    return 1

def check_table_is_present(db_path, table):
    table_name = sanitize_exp_name(table)
    conn = sqlite3.connect(db_path, timeout=50)
    c = conn.cursor()
    # check if table exists
    print('Check if {} table exists in the database:'.format(table_name))
    query = """SELECT delay FROM {};""".format(table_name)
    value = 0
    try:
        c.execute(query)
        value = False
    except sqlite3.Error:
        print("table not found")
    else:
        value = True
    return value