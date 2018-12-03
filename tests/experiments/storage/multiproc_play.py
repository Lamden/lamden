from cilantro.logger.base import get_logger
from multiprocessing import Process


class SharedClass:
    data = {}


def add_kv(k, v):
    l = get_logger("add_kv")
    l.info("BEFORE ADDING: {}".format(SharedClass.data))
    l.debug("adding {} {}".format(k, v))
    SharedClass.data[k] = v
    l.info("AFTER ADDING: {}".format(SharedClass.data))


def proc1():
    add_kv('p1.1', 'k1.1')
    add_kv('p1.2', 'k1.2')
    add_kv('p1.3', 'k1.3')
    add_kv('p1.4', 'k1.4')


def proc2():
    add_kv('p2.1', 'k2.1')
    add_kv('p2.2', 'k2.2')
    add_kv('p2.3', 'k2.3')
    add_kv('p2.4', 'k2.4')


if __name__ == "__main__":
    p1 = Process(target=proc1)
    p2 = Process(target=proc2)
    print("\n\nstarting\n\n")
    p1.start()
    p2.start()

    p1.join()
    p2.join()

    print("\n\ndone\n\n")
