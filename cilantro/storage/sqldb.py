import mysql.connector, cilantro, os
from configparser import SafeConfigParser

path = os.path.dirname(cilantro.__path__[0])
config = SafeConfigParser()
config.read('{}/db_conf.ini'.format(path))
encoding = 'binary'

class SQLDB():
    connection = None
    cursor = None
    database = config.get('DB','database')
    def __enter__(self, database=None, reset=False):
        database = database or self.database
        if self.connection == None:
            self.force_start()
        if reset:
            self.drop_db(database)
            self.setup_db(database)
        elif not self.connection.is_connected():
            self.force_start()
        return self.connection, self.cursor
    def __exit__(self, type, value, traceback):
        return False

    @classmethod
    def force_start(cls):
        cls.connection = mysql.connector.connect(
            host=config.get('DB','hostname'),
            user=config.get('DB','username'),
            passwd=config.get('DB','password'),
            charset=encoding
        )
        cls.cursor = cls.connection.cursor()
        cls.setup_db()

    @classmethod
    def setup_db(cls, database=None):
        if cls.connection == None:
            cls.force_start()
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
        if cls.cursor:
            cls.cursor.execute("""
                DROP DATABASE IF EXISTS {}
                """.format(database or cls.database))

    @classmethod
    def reset_db(cls, database=None):
        cls.drop_db(database)
        cls.setup_db(database)

    @classmethod
    def truncate_tables(cls, *tables):
        for table in tables:
            cls.cursor.execute("""
                TRUNCATE TABLE {}
            """.format(table))

    @classmethod
    def build_tables(cls):
        cls.cursor.execute("""
            CREATE TABLE IF NOT EXISTS subblock (
                merkle_root VARCHAR(64) PRIMARY KEY,
                signatures BLOB NOT NULL,
                merkle_leaves BLOB NOT NULL,
                sb_index INT NOT NULL
            )
        """)
        cls.cursor.execute("""
            CREATE TABLE IF NOT EXISTS block (
                block_num INT PRIMARY KEY AUTO_INCREMENT,
                block_hash VARCHAR(64) NOT NULL UNIQUE,
                merkle_roots TEXT NOT NULL,
                prev_block_hash VARCHAR(64) NOT NULL UNIQUE,
                mn_signature BLOB NOT NULL,
                ts TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
            )
        """)
        cls.cursor.execute("""
            CREATE TABLE IF NOT EXISTS transaction (
                tx_hash VARCHAR(64) PRIMARY KEY,
                block_hash VARCHAR(64) NOT NULL,
                raw_tx_hash VARCHAR(64) NOT NULL,
                contract_tx BLOB NOT NULL,
                status VARCHAR(16) NOT NULL,
                state BLOB NOT NULL
            )
        """)
