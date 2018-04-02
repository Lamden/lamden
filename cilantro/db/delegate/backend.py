import plyvel
import mysql.connector
from pypika import Query as Q
from pypika import Table as T

SEPARATOR = '/'
SCRATCH = 'scratch'
STATE = 'state'
BALANCES = 'balances'
TXQ = 'txq'
PATH = '/tmp/cilantro'
VOTES = 'votes'
SWAPS = 'swaps'


# def sync_state_with_scratch(backend):
#     scratch = backend.flush(SCRATCH)
#     for tx in scratch:
#         k, v = tx
#         k = k.lstrip(SCRATCH)
#         k = STATE + k
#         backend.set


class Backend:
    def get(self, table, key):
        raise NotImplementedError

    def set(self, table, key, value):
        raise NotImplementedError

    def exists(self, table, key):
        raise NotImplementedError

    def flush(self, table):
        raise NotImplementedError


class SQLBackend:
    def __init__(self, user='root'):
        self.context = mysql.connector.connect(user=user)
        self.db = self.context.cursor()

    def execute(self, q):
        self.db.execute(q)

    def select(self, table, conditions):
        self.db.execute('select * from {} where {};'.format(table, conditions))
        tx = self.db.fetchall()
        return tx

    def replace(self, table, fields, values):
        q = 'replace into {} {} values {};'.format(table, fields, values)
        print(q)
        self.db.execute(q)
        self.context.commit()

    def delete(self, table, conditions):
        self.db.execute('delete from {} where {};'.format(table, conditions))
        self.context.commit()

class LevelDBBackend(Backend):
    def __init__(self, path=PATH):
        self.path = path

    def get(self, table: bytes, key: bytes):
        db = plyvel.DB(self.path, create_if_missing=True)
        r = db.get(SEPARATOR.join([table, key]))
        db.close()
        return r

    def set(self, table: bytes, key: bytes, value: bytes):
        db = plyvel.DB(self.path, create_if_missing=True)
        if value is None:
            value = b''
        r = db.put(SEPARATOR.join([table, key]), value)
        db.close()
        return r

    def exists(self, table: bytes, key: bytes):
        db = plyvel.DB(self.path, create_if_missing=True)
        if db.get(SEPARATOR.join([table, key])) is not None:
            db.close()
            return True
        db.close()
        return False

    def delete(self, table: bytes, key: bytes):
        db = plyvel.DB(self.path, create_if_missing=True)
        db.delete(SEPARATOR.join([table, key]))
        db.close()

    def flush(self, table: bytes, return_results=True):
        results = []
        db = plyvel.DB(self.path, create_if_missing=True)
        for k, v in db.iterator(prefix=table):
            if return_results:
                results.append((k, v))
            db.delete(k)
        db.close()
        return results


class Database:
    def __init__(self, name, tables, cursor):
        self.name = name
        self.tables = tables
        self.db = cursor

    def setup(self):
        self.db.execute('create database if not exists {};'.format(self.name))
        self.db.execute('use {};'.format(self.name))
        [t.setup(self.db) for t in self.tables]


class Table:
    def __init__(self, name, columns, primary_key=None):
        self.name = name
        self.columns = columns
        self.primary_key = primary_key

    def setup(self, cursor):
        q = 'CREATE TABLE if not exists {}(\n'.format(self.name)

        for o in self.columns:
            q += '{} {},\n'.format(o[0], o[1])

        if self.primary_key is None:
            q = q[:-2] + '\n'
        else:
            q += 'primary key ({})\n'.format(self.primary_key)

        q += ');'
        cursor.execute(q)


class Query:
    def __init__(self, table, updates):
        self.table = table
        self.updates = updates


class TransactionQueue:
    def __init__(self, backend):
        self.backend = backend
        self.size = 0
        self.table_name = 'txq'

        txs = Table(name='txq', columns=[('id', 'int'), ('tx', 'blob')])
        txq = Database(name='txq', tables=[txs], cursor=self.backend)
        txq.setup()

    def push(self, tx):
        self.size += 1
        q = Q.into(self.table_name).columns('id', 'tx').insert(self.size, tx)
        self.backend.execute(q)

    def pop(self):
        q = Q.from_(T('txq')).select('*').where(T('txq').id == 0)
        tx = self.backend.execute(q)
        q = 'DELETE FROM {} WHERE "id"={}'.format(self.table_name, self.size)
        self.backend.execute(q)
        self.size -= 1
        return tx

    def flush(self):
        q = Q.from_(T('txq')).select('*')
        tx = self.backend.execute(q)
        self.backend.execute('DROP TABLE {};'.format(self.table_name))
        return tx
