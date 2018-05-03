from cilantro.logger import get_logger
from multiprocessing import Process
import time




class Breaker:
    def __init__(self):
        self.log = get_logger("Breaker")
        log.info("Breaker created")

    def explode(self):
        log.info("EXPLODING")
        # d = self.some_func('a', 'b', 'c')
        d = getattr(self, 'some_func')(self, 'a', 'b')
        log.debug("got d: {}".format(d))


    def some_func(self, param1, param2):
        log.debug("running some func with p1: {}, p2: {}".format(param1, param2))
        return "hi {}, {}".format(param1, param2)

def a():
    log = get_logger("A")
    log.info("A something started")
    b = Breaker()
    b.explode()

def b():
    log = get_logger("B")
    log.info("B something started")


if __name__ == "__main__":
    log = get_logger("Main")
    log.info("Main started")

    p1 = Process(target=a)
    p2 = Process(target=b)
    p1.start()
    p2.start()

    time.sleep(10)
    log.info("Main over")

