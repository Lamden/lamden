from multiprocessing import Lock, Process
from cilantro.logger import get_logger
import time
import random

DB_NAME = 'cilantro'


class DBSingletonMeta(type):
    __lock = Lock()
    # _instances = {}
    LOCK, INSTANCE = 'LOCK', 'INSTANCE'

    def __new__(cls, clsname, bases, clsdict):
        clsobj = super().__new__(cls, clsname, bases, clsdict)
        print("Creating singleton meta for clsname: {} and clsobj {}".format(clsname, clsobj))
        if not hasattr(clsobj, '_instances'):
            print("****Creating _instances dictionary")
            clsobj._instances = {'hello' : 'ass'}

        return clsobj

    def __call__(cls, db_suffix='', db_name=DB_NAME):
        # if not hasattr(DBSingletonMeta, '_instances'):
        #     print("Creating _instances for cls {}".format(DBSingletonMeta))
        #     DBSingletonMeta._instances = {}
        print("call invoked on cls {} with _instances {} ... requesting DBSingleton lock".format(cls, cls._instances))
        with DBSingletonMeta.__lock:
            if db_suffix:
                db_name = "{}_{}".format(db_name, db_suffix)

            if db_name not in cls._instances:
                print("\n\n~~~ Creating singleton for class {} with db_name: {}".format(cls.__name__, db_name))
                cls._instances[db_name] = super().__call__(db_name)
                print("~~~ Done creating singleton...")
                # cls._instances[db_name][DBSingletonMeta.INSTANCE] = super().__call__(db_name)
                # cls._instances[db_name][DBSingletonMeta.LOCK] = Lock()
            print("rleasing DBSingleton lock")
            print("new cls._instances: {}".format(cls._instances))
            return cls._instances[db_name]


class DB(metaclass=DBSingletonMeta):
    def __init__(self, db_name):
        print("\n\nDB created with db_name {}\n\n".format(db_name))
        self.db_name = db_name
        self.lock = Lock()

    def __enter__(self):
        print("ENTER CALLED ON {} WITH DB NAME {}".format(self, self.db_name))
        print("aquiring lock {}".format(self.lock))
        self.lock.acquire()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        print("EXIT CALLED ON {} WITH DB NAME {}".format(self, self.db_name))
        print("releasing lock {}".format(self.lock))
        self.lock.release()


# class ObjectA(metaclass=DBSingletonMeta): pass

# a = DB('hello')
# b = DB()
# c = DB('hello')
#
# print(a == b)
# print(a==c)
# assert a is c, "c is not a"
# print(a)
# print(b)

# log = get_logger("Main")




def do1():
    log = get_logger("do1")
    with DB() as db:
        log.debug("[1] hey i got db: {}".format(db))
        log.debug("sleeping for 2 seconds")
        time.sleep(2)
        log.debug("done sleeping for 2")

def do2():
    log = get_logger("***do2")
    with DB() as db:
        log.debug("[2] hey i got db: {}".format(db))
        log.debug("sleeping for another 2 seconds")
        time.sleep(2)
        log.debug("done sleeping for 2")

p1 = Process(target=do1)
p2 = Process(target=do2)

log = get_logger("Main")
DB()
log.debug("Starting processes...")
p1.start()
p2.start()
# time.sleep(0.5)
log.debug("Processes started.")
# time.sleep(3)
# print(DB._instances)