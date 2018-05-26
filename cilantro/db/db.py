"""The db module for delegate is for bootstrapping the in-memory database for delegate nodes to store scratch and
execute smart contracts

Functions include:
-create_db
-execute (execute smart contract query)

Classes include:
-DBSingletonMeta
-DB (which inherits from DBSingletonMeta)
"""

from multiprocessing import Lock
import os, json
from cilantro.logger import get_logger
from sqlalchemy import *
from sqlalchemy.sql.visitors import *
from sqlalchemy.sql.sqltypes import *
from sqlalchemy.sql.functions import coalesce
from sqlalchemy.sql.selectable import Select
from sqlalchemy import select, insert, update, delete, and_

from functools import wraps

DB_NAME = 'cilantro'
SCRATCH_PREFIX = 'scratch_'


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
            # Dynamically inject 'tables' into namespace of function to use this context's instance of db
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
    log.info("Creating MySQLAlchemy DB connection for DB with name {}".format(name))

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
        log.critical("Dropping database...")
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
        log.critical("\n\n database {} not found, seeding that shit \n\n".format(name))

        masternodes = []
        delegates = []
        witnesses = []

        # add state for tables that are not masternodes and delegates as those get treated differently
        for k in constitution_json.keys():
            for item in constitution_json[k]:
                if k != 'masternodes' and k != 'delegates' and k != 'witnesses':
                    t = getattr(tables, k)
                    db.execute(t.insert(item))
                elif k == 'masternodes':
                    masternodes.append(item)
                elif k == 'delegates':
                    delegates.append(item)
                elif k == 'witnesses':
                    witnesses.append(item)

        # add the masternodes and delegates to the policy table. this is so that users can easily add wallets to the
        # constitution and
        t = getattr(tables, 'constants')
        db.execute(t.insert(get_policy_for_node_list(masternodes, 'masternodes')))
        db.execute(t.insert(get_policy_for_node_list(delegates, 'delegates')))
        db.execute(t.insert(get_policy_for_node_list(witnesses, 'witnesses')))

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


class DBSingletonMeta(type):
    _lock = Lock()
    _contexts = {}
    _instances = {}
    log = get_logger("DBSingleton")

    def __call__(cls, db_name=DB_NAME, should_reset=False):
        """
        Intercepts the init of the DB class to make it behave like a singleton.
        - Each process should have its own 'context', which has a unique DB instance for each db name as well as a
          default instance which you can set with DB.set_context(db_name)
        - Each unique DB name will have it's own singleton instance.
        - DB names are denoted by arg 'db_name'

        :param db_name: The name of the db to create
        :return: A DB instance
        """
        cls.log.debug("(__call__) Acquiring DBSingleton lock {}".format(DBSingletonMeta._lock))
        with DBSingletonMeta._lock:
            instance_id = DBSingletonMeta._instance_id(db_name)
            pid = os.getpid()

            # Set default context for this process if not already set
            if pid in cls._contexts:
                # If called without any args, use default context
                if db_name == DB_NAME:
                    instance_id = cls._contexts[pid]
                    db_name = DBSingletonMeta._db_name(instance_id)
                    cls.log.debug("Process found default instance id {} in _contexts: {}".format(instance_id, cls._contexts))
            else:
                cls._contexts[pid] = instance_id
                cls.log.debug("Setting default context for pid {} to instance id {} ... _contexts: {}"
                              .format(pid, instance_id, cls._contexts))

            # Instantiate an instance of DB for instance_id if it does not exist
            if instance_id not in cls._instances:
                cls._instances[instance_id] = super(DBSingletonMeta, cls).__call__(db_name, should_reset=should_reset)

            cls.log.debug("(__call__) Releasing DBSingleton lock {}".format(DBSingletonMeta._lock))
            return cls._instances[instance_id]

    @staticmethod
    def _instance_id(db_name):
        return "{}_{}".format(os.getpid(), db_name)

    @staticmethod
    def _db_name(instance_id):
        return instance_id[instance_id.find('_') + 1:]

    @classmethod
    def set_context(cls, db_name):
        cls.log.debug("setting context for pid {} with db name: {}".format(os.getpid(), db_name))
        cls._contexts[os.getpid()] = cls._instance_id(db_name)


class DB(metaclass=DBSingletonMeta):
    def __init__(self, db_name, should_reset):
        self.db_name = db_name
        self.log = get_logger("DB-{}".format(db_name))
        self.log.info("Creating DB instance for {} with should_reset={}".format(db_name, should_reset))
        self.lock = Lock()

        self.db, self.tables = create_db(db_name, should_reset)

    def __enter__(self):
        self.log.debug("Acquiring lock {}".format(self.lock))
        self.lock.acquire()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.log.debug("Releasing lock {}".format(self.lock))
        self.lock.release()

    def execute(self, query):
        self.log.debug("Executing query {}".format(query))
        return self.db.execute(query)


class VKBook:

    @staticmethod
    def _destu_ify(data: str):
        assert len(data) % 64 == 0, "Length of data should be divisible by 64! Logic error!"
        li = []
        for i in range(0, len(data), 64):
            li.append(data[i:i+64])
        return li

    @staticmethod
    def _get_vks(policy: str):
        with DB() as db:
            q = db.execute("select value from constants where policy='{}'".format(policy))
            rows = q.fetchall()

            val = rows[0][0]

            return VKBook._destu_ify(val)

    @staticmethod
    def get_masternodes():
        return VKBook._get_vks('masternodes')

    @staticmethod
    def get_delegates():
        return VKBook._get_vks('delegates')

    @staticmethod
    def get_witnesses():
        return VKBook._get_vks('witnesses')
