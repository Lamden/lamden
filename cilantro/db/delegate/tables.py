from sqlalchemy import *

DATABASE = 'blockchain'
SCRATCH_PREFIX = 'scratch_'

# connect to the mysql instance
db = create_engine('mysql+pymysql://root@localhost')
metadata = MetaData()

# create the tables that we want / need for our smart contracts
balances = Table('balances', metadata,
                 Column('wallet', String(64), primary_key=True),
                 Column('amount', Float(precision=4), nullable=False))

swaps = Table('swaps', metadata,
              Column('sender', String(64), primary_key=True),
              Column('receiver', String(64), nullable=False),
              Column('amount', Float(precision=4), nullable=False),
              Column('expiration', Integer, nullable=False),
              Column('hashlock', String(40), nullable=False))

votes = Table('votes', metadata,
              Column('wallet', String(64), nullable=False),
              Column('policy', String(64), nullable=False),
              Column('choice', String(64), nullable=False))

mapping = {}

# create copies of the tables to hold temporary scratch by iterating through the metadata
for table in metadata.sorted_tables:
    columns = [c.copy() for c in table.columns]
    scratch_table = Table('{}{}'.format(SCRATCH_PREFIX, table.name), metadata, *columns)
    mapping[table] = scratch_table

db.execute('create database if not exists {}'.format(DATABASE))
db.execute('use {};'.format(DATABASE))
metadata.create_all(db)
