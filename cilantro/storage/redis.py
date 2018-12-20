from seneca.constants.config import *
import os, threading
import redis
from multiprocessing import Lock


class SafeRedisMeta(type):
    """
    A simple Redis Driver designed to be used functionally across multiple threads/procs.
    Each thread will get its own cursor.
    """
    _shared_state = {}
    # We only need the lock if we are going to be using threads. Each process should have their own copy of this class
    # _lock = Lock()

    def _get_key(cls) -> str:
        # uncomment below for thread locking
        # key = "{}:{}".format(os.getpid(), threading.get_ident())

        key = str(os.getpid())
        return key

    def cleanup(cls):
        print('Redis is cleaning up!')
        cls._shared_state.clear()

    def __getattr__(cls, item):
        key = cls._get_key()
        if key in cls._shared_state:
            cur = cls._shared_state[key]
        else:
            cur = redis.StrictRedis(host='localhost', port=get_redis_port(), db=MASTER_DB, password=get_redis_password())
            cls._shared_state[key] = cur

        return getattr(cur, item)


class SafeRedis(metaclass=SafeRedisMeta):
    pass
