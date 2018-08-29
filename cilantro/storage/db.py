"""The storage module for delegate is for bootstrapping the in-memory database for delegate nodes to store scratch and
execute smart contracts

Functions include:
-create_db
-execute (execute smart contract query)

Classes include:
-DBSingletonMeta
-DB (which inherits from DBSingletonMeta)
"""

from seneca.engine.storage.mysql_executer import Executer

from multiprocessing import Lock
import os
import math
from cilantro.logger import get_logger
from functools import wraps

# TODO remove this stuff once we can 100% deprecate it
from sqlalchemy import *
from sqlalchemy.sql.visitors import *
from sqlalchemy.sql.sqltypes import *
from sqlalchemy.sql.functions import coalesce
from sqlalchemy.sql.selectable import Select
from sqlalchemy import select, insert, update, delete, and_


from cilantro.storage.tables import build_tables, _reset_db
from cilantro.constants.db import DB_SETTINGS

DB_NAME = 'cilantro'
SCRATCH_PREFIX = 'scratch_'


log = get_logger("DB")


constitution_json = json.load(open(os.path.join(os.path.dirname(__file__), 'constitution.json')))


def get_policy_for_node_list(l, name):
    payload = ''.join(sorted(l))
    p = {
        "policy": name,
        "type": "multi_discrete",
        "last_election_start" : 0,
        "last_election_end" : 0,
        "election_length": 168,
        "election_frequency": 336,
        "max_votes": 0,
        "value": payload,
        "in_vote": False,
        "round": 0,
        "permissions": 7
    }
    return p


def contract(tx_type):
    def decorate(tx_func):
        # print("Setting tx type {} to use contract {}".format(tx_type, tx_func))
        tx_type.contract = tx_func

        @wraps(tx_func)
        def format_query(*args, compile_deltas=True, **kwargs):
            # Dynamically inject 'tables' into namespace of function to use this context's instance of storage
            with DB() as db:
                # print("\ndynamically injecting tables\n")
                tx_func.__globals__['tables'] = db.tables

            deltas = tx_func(*args, **kwargs)

            if deltas is None:
                return None

            if not compile_deltas:
                return deltas

            try:
                deltas[0]
            except TypeError:
                deltas = [deltas]

            new_deltas = []
            for delta in deltas:
                new_deltas.append(str(delta.compile(compile_kwargs={'literal_binds': True})))

            return new_deltas

        return format_query
    return decorate


def execute(query, check_scratch=True):
    if check_scratch and type(query) == Select:
        # modify it to look at scratch first
        scratch_q = ScratchCloningVisitor().traverse(query)
        query = coalesce(scratch_q.as_scalar(), query.as_scalar())

    with DB() as db:
        result = db.execute(query)
        return result


def create_db(name, should_reset=False):
    log = get_logger("DBCreator")
    log.info("Creating DB connection for DB with name {}".format(name))

    # ex = Executer.init_local_noauth_dev(db_name=name)
    db = create_engine('mysql+pymysql://root@localhost')
    metadata = MetaData()

    # create the tables that we want / need for our smart contracts
    balances = Table('balances', metadata,
                     Column('wallet', String(64)),
                     Column('amount', Float(precision=4), nullable=False))

    swaps = Table('swaps', metadata,
                  Column('sender', String(64)),
                  Column('receiver', String(64), nullable=False),
                  Column('amount', Float(precision=4), nullable=False),
                  Column('expiration', Integer, nullable=False),
                  Column('hashlock', String(64), nullable=False))

    votes = Table('votes', metadata,
                  Column('wallet', String(64), nullable=False),
                  Column('policy', String(64), nullable=False),
                  Column('choice', String(64), nullable=False),
                  Column('round', Integer))

    stamps = Table('stamps', metadata,
                   Column('wallet', String(64)),
                   Column('amount', Float(precision=4), nullable=False))

    constants = Table('constants', metadata,
                      Column('policy', String(64), nullable=False),
                      Column('type', Enum('discrete', 'continuous', 'multi_discrete', name='variable'), nullable=False),
                      Column('last_election_start', DateTime, nullable=False), # represented as unix time stamp to minute
                      Column('last_election_end', DateTime, nullable=False),
                      Column('election_length', Integer, nullable=False), # represented in minutes
                      Column('election_frequency', Integer, nullable=False), # represented in minutes
                      Column('max_votes', Integer, nullable=False),
                      Column('value', TEXT, nullable=True),
                      Column('in_vote', Boolean, nullable=False),
                      Column('permissions', Integer, nullable=False),
                      Column('round', Integer, nullable=False))

    blocks = Table('blocks', metadata,
                   Column('number', Integer, primary_key=True, autoincrement=True),
                   Column('hash', String(64), nullable=False),
                   Column('tree', TEXT, nullable=False),
                   Column('signatures', TEXT, nullable=False))

    state_meta = Table('state_meta', metadata,
                        Column('number', Integer,),
                        Column('hash', String(64), nullable=False))

    transactions = Table('transactions', metadata,
                         Column('key', String(64), nullable=False),
                         Column('value', TEXT, nullable=False))

    mapping = {}

    tables = type('Tables', (object,),
                  {'balances': balances,
                   'swaps': swaps,
                   'votes': votes,
                   'stamps': stamps,
                   'constants': constants,
                   'blocks': blocks,
                   'transactions': transactions,
                   'state_meta': state_meta,
                   'mapping': mapping})

    # create copies of the tables to hold temporary scratch by iterating through the metadata
    for table in metadata.sorted_tables:
        columns = [c.copy() for c in table.columns]
        scratch_table = Table('{}{}'.format(SCRATCH_PREFIX, table.name), metadata, *columns)
        mapping[table] = scratch_table

    # reset database if specified
    if should_reset:
        log.debug("Dropping database...")
        db.execute('drop database if exists {}'.format(name))
        log.debug("Database dropped.")

    # Check if database exists before we create it. If it doesn't we seed it later
    dbs = db.execute('show databases')
    db_names = [d[0] for d in dbs.fetchall()]

    # Create database if it doesnt exist
    db.execute('create database if not exists {}'.format(name))
    db.execute('use {};'.format(name))
    metadata.create_all(db)

    # Seed database if it is newly created
    if name not in db_names:

        masternodes = []
        delegates = []
        witnesses = []

        # add state for tables that are not TESTNET_MASTERNODES and TESTNET_DELEGATES as those get treated differently
        for k in constitution_json.keys():
            for item in constitution_json[k]:
                if k != 'TESTNET_MASTERNODES' and k != 'TESTNET_DELEGATES' and k != 'TESTNET_WITNESSES':
                    t = getattr(tables, k)
                    db.execute(t.insert(item))
                elif k == 'TESTNET_MASTERNODES':
                    masternodes.append(item)
                elif k == 'TESTNET_DELEGATES':
                    delegates.append(item)
                elif k == 'TESTNET_WITNESSES':
                    witnesses.append(item)

        # add the TESTNET_MASTERNODES and TESTNET_DELEGATES to the policy table. this is so that users can easily add wallets to the
        # constitution and
        t = getattr(tables, 'constants')
        db.execute(t.insert(get_policy_for_node_list(masternodes, 'TESTNET_MASTERNODES')))
        db.execute(t.insert(get_policy_for_node_list(delegates, 'TESTNET_DELEGATES')))
        db.execute(t.insert(get_policy_for_node_list(witnesses, 'TESTNET_WITNESSES')))

    # log.debug("\n\n got dbs: \n{}\n\n".format(dbs.fetchall()))
    return db, tables


class ScratchCloningVisitor(CloningVisitor):

    def __init__(self):
        super().__init__()
        print('creating ScratchCloningVisitor')  # debug line, remove later
        with DB() as db:
            self.tables = db.tables

    def replace(self, elem):
        # replace tables with scratch tables
        if elem.__class__ == Table:
            return self.tables.mapping[elem]
        # replace columns with scratch equivalents
        elif elem.__class__ == Column:
            if elem.table.__class__ == Table:
                scr_tab = self.tables.mapping[elem.table]
                cols = [c for c in scr_tab.columns if c.name == elem.name]
                return cols[0]

        return None

    def traverse(self, obj):
        # traverse and visit the given expression structure.

        def replace(elem):
            for v in self._visitor_iterator:
                e = v.replace(elem)
                if e is not None:
                    return e

        return replacement_traverse(obj, self.__traverse_options__, replace)

def reset_db():
    def clear_instances():
        log.info("Clearing {} db instances...".format(len(DBSingletonMeta._instances)))
        for instance in DBSingletonMeta._instances.values():
            instance.ex.cur.close()
            instance.ex.conn.close()
        DBSingletonMeta._instances.clear()
        log.info("DB instances cleared.")

    clear_instances()

    ex = Executer(**DB_SETTINGS)
    _reset_db(ex)

    ex.cur.close()
    ex.conn.close()


class DBSingletonMeta(type):
    _lock = Lock()
    _instances = {}
    log = get_logger("DBSingleton")

    def __call__(cls, should_reset=False):
        """
        Intercepts the init of the DB class to make it behave like a singleton. Each process has its own instance, which
        is lazily created.
        :return: A DB instance
        """
        pid = os.getpid()

        # Instantiate an instance of DB for this process if it does not exist
        if pid not in cls._instances:
            cls._instances[pid] = super(DBSingletonMeta, cls).__call__(should_reset=should_reset)

        return cls._instances[pid]


class DB(metaclass=DBSingletonMeta):
    def __init__(self, should_reset):
        self.log = get_logger("DB")
        self.log.info("Creating DB instance with should_reset={}".format(should_reset))

        self.lock = Lock()

        self.ex = Executer(**DB_SETTINGS)
        self.tables = build_tables(self.ex, should_drop=should_reset)

    def __enter__(self):
        self.log.debug("Acquiring lock {}".format(self.lock))
        self.lock.acquire()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.log.debug("Releasing lock {}".format(self.lock))
        self.lock.release()

from cilantro.constants.testnet import TESTNET_DELEGATES, TESTNET_WITNESSES, TESTNET_MASTERNODES
class VKBook:

    MASTERNODES = [node['vk'] for node in TESTNET_MASTERNODES]
    WITNESSES = [node['vk'] for node in TESTNET_WITNESSES]
    DELEGATES = [node['vk'] for node in TESTNET_DELEGATES]

    # DELEGATES = [
    #   "3dd5291906dca320ab4032683d97f5aa285b6491e59bba25c958fc4b0de2efc8",
    #   "ab59a17868980051cc846804e49c154829511380c119926549595bf4b48e2f85",
    #   "0c998fa1b2675d76372897a7d9b18d4c1fbe285dc0cc795a50e4aad613709baf"
    # ]
    # WITNESSES = [
    #   "0e669c219a29f54c8ba4293a5a3df4371f5694b761a0a50a26bf5b50d5a76974",
    #   "50869c7ee2536d65c0e4ef058b50682cac4ba8a5aff36718beac517805e9c2c0",
    #   # "d2bf672139c73b70e7b81668c3f7f596679203828d0034908c41c8a8e43444ed",
      # "ca0355e4b1e68751b09f47281f077e4dac32948a78341958efef964840e299f2",
      # "c9da4d9862bc9ef140989456c36f83af4c3e218b6a0d2c56f97128d3db0db9d3"
    # ]

    @staticmethod
    def get_all():
        return VKBook.MASTERNODES + VKBook.DELEGATES + VKBook.WITNESSES

    @staticmethod
    def get_masternodes():
        return VKBook.MASTERNODES

    @staticmethod
    def get_delegates():
        return VKBook.DELEGATES

    @staticmethod
    def get_witnesses():
        return VKBook.WITNESSES

    @staticmethod
    def get_delegate_majority():
        return math.ceil(len(VKBook.get_delegates()) * 2/3)
