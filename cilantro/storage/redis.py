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
        key = "{}:{}".format(os.getpid(), threading.get_ident())
        return key

    def cleanup(cls):
        with cls._lock:
            cls._shared_state.clear()

    def __getattr__(cls, item):
        # First see if there is a cursor for this proccess
        key = cls._get_key()

        # TODO do i need to put this check in a lock? I might...
        if key in cls._shared_state:
            return cls._shared_state[key]
        else:
            with cls._lock:
                cursor = redis.StrictRedis(host='localhost', port=get_redis_port(), db=MASTER_DB, password=get_redis_password())
                cls._shared_state[key] = cursor



class SafeRedis(metaclass=SafeRedisMeta):
    pass



