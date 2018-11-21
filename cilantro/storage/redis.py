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
    _lock = Lock()

    def _get_key(cls) -> str:
        # uncomment below for thread locking
        # key = "{}:{}".format(os.getpid(), threading.get_ident())

        key = str(os.getpid())
        return key

    def cleanup(cls):
        with cls._lock:
            # TODO do we need to close all cursors?
            cls._shared_state.clear()

    def __getattr__(cls, item):
        # key = cls._get_key()
        # with cls._lock:
        #     if key in cls._shared_state:
        #         cur = cls._shared_state[key]
        #     else:
        #         cur = redis.StrictRedis(host='localhost', port=get_redis_port(), db=MASTER_DB, password=get_redis_password())
        #         cls._shared_state[key] = cur
        #
        #     return getattr(cur, item)

        key = cls._get_key()
        if key in cls._shared_state:  # TODO does this need to be in a lock? maybe...
            cur = cls._shared_state[key]
        else:
            with cls._lock:
                cur = redis.StrictRedis(host='localhost', port=get_redis_port(), db=MASTER_DB, password=get_redis_password())
                cls._shared_state[key] = cur

        return getattr(cur, item)


class SafeRedis(metaclass=SafeRedisMeta):
    pass



