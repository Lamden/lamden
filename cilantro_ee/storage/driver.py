from cilantro_ee.constants.db_config import *
from contracting.db.driver import DatabaseDriver
import os, threading
from multiprocessing import Lock


class SafeDriverMeta(type):
    """
    A simple Redis Driver designed to be used functionally across multiple threads/procs.
    Each thread will get its own cursor.
    """
    _shared_state = {}
    # We only need the lock if we are going to be using threads. Each process should have their own copy of this class
    # _lock = Lock()

    def _get_key(cls) -> str:
        # uncomment below for thread level locking
        # key = "{}:{}".format(os.getpid(), threading.get_ident())

        key = str(os.getpid())
        return key

    def cleanup(cls):
        print('SafeDriver is cleaning up!')
        cls._shared_state.clear()

    def __getattr__(cls, item):
        key = cls._get_key()
        if key in cls._shared_state:
            cur = cls._shared_state[key]
        else:
            cur = DatabaseDriver()
            cls._shared_state[key] = cur

        return getattr(cur, item)


class SafeDriver(metaclass=SafeDriverMeta):
    pass


