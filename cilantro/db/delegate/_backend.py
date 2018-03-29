import mysql.connector
from pypika import Query
from pypika import Table as T


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

# context = mysql.connector.connect(user='root')
# db = context.cursor()
#
# balances = Table(name='balances', columns=[('wallet', 'text'), ('amount', 'int')])
#
# votes = Table(name='votes', columns=[
#     ('policy', 'text'),
#     ('choice', 'text'),
#     ('wallet', 'text')])
#
# swaps = Table(name='swaps', columns=[
#     ('sender', 'text'),
#     ('receiver', 'text'),
#     ('amount', 'int'),
#     ('hashlock', 'text'),
#     ('expiration', 'text'),
# ])
#
# standard_tables = [balances, votes, swaps]
#
# state = Database(name='state', tables=standard_tables, cursor=db)
# scratch = Database(name='scratch', tables=standard_tables, cursor=db)
#
# state.setup()
# scratch.setup()

# txs = Table(name='txq', columns=[('id', 'int'), ('tx', 'blob')])
#
# txq = Database(name='txq', tables=[txs], cursor=db)

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
        q = Query.into(self.table_name).columns('id', 'tx').insert(self.size, tx)
        self.backend.execute(q)

    def pop(self):
        q = Query.from_(T('txq')).select('*').where(txq.id == 0)
        tx = self.backend.execute(q)
        tx = tx.fetchone()
        q = 'DELETE FROM {} WHERE "id"={}'.format(self.table_name, self.size)
        self.backend.execute(q)
        self.size -= 1
        return tx

    def flush(self):
        q = Query.from_(T('txq')).select('*')
        tx = self.backend.execute(q)
        tx = tx.fetchall()
        self.backend.execute('DROP TABLE {};'.format(self.table_name))
        return tx