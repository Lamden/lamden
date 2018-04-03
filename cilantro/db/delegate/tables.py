from sqlalchemy import *

db = create_engine('mysql+pymysql://root@localhost')
metadata = MetaData()

balances = Table('balances', metadata,
                 Column('wallet', String(64), primary_key=True),
                 Column('amount', Float(precision=4), nullable=False))

swaps = Table('swaps', metadata,
              Column('sender', String(64), primary_key=True),
              Column('receiver', String(64), nullable=False),
              Column('amount', Float(precision=4), nullable=False),
              Column('expiration', Date, nullable=False),
              Column('hashlock', String(40), nullable=False))

votes = Table('votes', metadata,
              Column('wallet', String(64), nullable=False),
              Column('policy', String(64), nullable=False),
              Column('choice', String(64), nullable=False))

db.execute('use state;')
metadata.create_all(db)

db.execute('use scratch;')
metadata.create_all(db)
