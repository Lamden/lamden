import mysql, mysql.connector, cilantro
from ConfigParser import SafeConfigParser

path = cilantro.__path__._path[0]
config = SafeConfigParser()
config.read('{}/db_conf.ini'.format(path))

class SQLDB():
    connection = mysql.connector.connect(
        host=config.get('hostname'),
        user=config.get('username'),
        passwd=config.get('password'),
        unix_socket='/tmp/mysql.sock',
        charset='utf8'
    )
    cursor = connection.cursor()
    database = config.get('database')
    def __enter__(self, database=None, reset=False):
        database = database or cls.database
        if reset:
            self.drop_db(database)
            self.setup_db(database)
        return self.connection, self.cursor
    def __exit__(self, type, value, traceback):
        self.connection.commit()
        return False
    @classmethod
    def setup_db(cls, database=None):
        database = database or cls.database
        cls.cursor.execute("""
            CREATE DATABASE IF NOT EXISTS {}
            """.format(database))
        cls.cursor.execute("""
            USE {}
            """.format(database))
        cls.build_tables()
    @classmethod
    def drop_db(cls, database=None):
        cls.cursor.execute("""
            DROP DATABASE IF EXISTS {}
            """.format(database or cls.database))
    @classmethod
    def build_tables(cls):
        cls.cursor.execute("""
            CREATE TABLE IF NOT EXISTS subblock (
                merkle_root VARCHAR(32) PRIMARY KEY,
                signatures BLOB NOT NULL,
                merkle_leaves BLOB NOT NULL,
                sb_index INT NOT NULL
            )
        """)
        cls.cursor.execute("""
            CREATE TABLE IF NOT EXISTS block (
                block_hash VARCHAR(32) PRIMARY KEY,
                merkle_roots BLOB NOT NULL,
                prev_block_hash BLOB NOT NULL,
                mn_signature VARCHAR(32) NOT NULL,
                ts TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
            )
        """)
        cls.cursor.execute("""
            CREATE TABLE IF NOT EXISTS transaction (
                tx_hash VARCHAR(32) PRIMARY KEY,
                raw_tx_hash VARCHAR(32) NOT NULL,
                tx_blob BLOB NOT NULL,
                status VARCHAR(16) NOT NULL,
                state VARCHAR(16) NOT NULL,
            )
        """)

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('-d', '--drop', action='store_true', default=False)
    parser.add_argument('-b', '--build-tables', action='store_true', default=False)
    args = parser.parse_args()
    if args.drop:
        SQLDB.drop_db()
    SQLDB.setup_db()
else:
    SQLDB.setup_db()
