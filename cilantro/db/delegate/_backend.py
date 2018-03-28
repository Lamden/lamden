import mysql.connector
from pypika import *

class Database:
    def __init__(self, name, tables, cursor):
        self.name = name
        self.tables = tables
        self.db = cursor

    def setup(self):
        self.db.execute('create database if not exists {};'.format(self.name))
        self.db.execute('use {};'.format(self.name))
        [t.setup() for t in self.tables]


class Table:
    def __init__(self, name, objects, cursor, primary_key=None):
        self.name = name
        self.objects = objects
        self.db = cursor
        self.primary_key = primary_key

    def setup(self):
        q = 'CREATE TABLE {}(\n'.format(self.name)

        for o in self.objects:
            q += '{} {},\n'.format(o[0], o[1])

        if self.primary_key is None:
            q = q[:-2] + '\n'
        else:
            q += 'primary key ({})\n'.format(self.primary_key)

        q += ');'
        self.db.execute(q)

class Backend:
    def __init__(self, user='root'):
        self.context = mysql.connector.connect(user=user)
        self.db = self.context.cursor()

    def create_db(self, name):
        self.db.execute('create database if not exists {};'.format(name))

    def use_db(self, name):
        self.db.execute('use database {};'.format(name))

