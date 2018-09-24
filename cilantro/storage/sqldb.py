import mysql, mysql.connector, cilantro
from ConfigParser import SafeConfigParser

path = cilantro.__path__._path[0]
parser = SafeConfigParser()
parser.read('{}/db_conf.ini'.format(path))

class SQLDB():
    connection = mysql.connector.connect(
        host=parser.get('hostname'),
        user=parser.get('username'),
        passwd=parser.get('password'),
        unix_socket='/tmp/mysql.sock',
        charset='utf8'
    )
    cursor = connection.cursor()
    database = parser.get('database')
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
            CREATE TABLE IF NOT EXISTS subblocks (
                merkle_root VARCHAR(32) PRIMARY KEY,
                signatures BLOB NOT NULL,
                merkle_leaves BLOB NOT NULL,
                sb_index INT NOT NULL
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
