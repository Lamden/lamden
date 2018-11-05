"""The storage module for delegate is for bootstrapping the in-memory database for delegate nodes to store scratch and
execute smart contracts

Functions include:
-create_db
-execute (execute smart contract query)

Classes include:
-DBSingletonMeta
-DB (which inherits from DBSingletonMeta)
"""

# from seneca.engine.storage.mysql_executer import Executer

from multiprocessing import Lock
import os
import math
from cilantro.logger import get_logger
from functools import wraps

from cilantro.storage.tables import build_tables, _reset_db
from cilantro.constants.db import DB_SETTINGS

DB_NAME = 'cilantro'
SCRATCH_PREFIX = 'scratch_'


log = get_logger("DB")


# def reset_db():
#     def clear_instances():
#         log.info("Clearing {} db instances...".format(len(DBSingletonMeta._instances)))
#         for instance in DBSingletonMeta._instances.values():
#             instance.ex.cur.close()
#             instance.ex.conn.close()
#         DBSingletonMeta._instances.clear()
#         log.info("DB instances cleared.")
#
#     clear_instances()
#
#     ex = Executer(**DB_SETTINGS)
#     _reset_db(ex)
#
#     ex.cur.close()
#     ex.conn.close()


# class DBSingletonMeta(type):
#     _lock = Lock()
#     _instances = {}
#     log = get_logger("DBSingleton")
#
#     def __call__(cls, should_reset=False):
#         """
#         Intercepts the init of the DB class to make it behave like a singleton. Each process has its own instance, which
#         is lazily created.
#         :return: A DB instance
#         """
#         pid = os.getpid()
#
#         # Instantiate an instance of DB for this process if it does not exist
#         if pid not in cls._instances:
#             cls._instances[pid] = super(DBSingletonMeta, cls).__call__(should_reset=should_reset)
#
#         return cls._instances[pid]


# class DB(metaclass=DBSingletonMeta):
#     def __init__(self, should_reset):
#         self.log = get_logger("DB")
#         self.log.info("Creating DB instance with should_reset={}".format(should_reset))
#
#         self.lock = Lock()
#
#         self.ex = Executer(**DB_SETTINGS)
#         self.tables = build_tables(self.ex, should_drop=should_reset)
#
#     def __enter__(self):
#         self.log.debug("Acquiring lock {}".format(self.lock))
#         self.lock.acquire()
#         return self
#
#     def __exit__(self, exc_type, exc_val, exc_tb):
#         self.log.debug("Releasing lock {}".format(self.lock))
#         self.lock.release()


from cilantro.constants.testnet import TESTNET_DELEGATES, TESTNET_WITNESSES, TESTNET_MASTERNODES
class VKBook:

    MASTERNODES = [node['vk'] for node in TESTNET_MASTERNODES]
    WITNESSES = [node['vk'] for node in TESTNET_WITNESSES]
    DELEGATES = [node['vk'] for node in TESTNET_DELEGATES]

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
