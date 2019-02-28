from multiprocessing import Process
from cilantro_ee.logger import get_logger
import time


class MyClass:
    def __init__(self, val):
        self.val = val

    def __repr__(self):
        return "class with val {} and id {}".format(self.val, id(self))


def build_class(val):
    log = get_logger("Test")
    c = MyClass(val)
    log.debug("Class: {}".format(c))

    if val == 'p1':
        log.debug("p1 detecting. sleeping and setting to pNEW")
        time.sleep(0.25)
        c.val = 'pNEW'
    else:
        time.sleep(0.5)

    log.debugv("class after possible wait: {}".format(c))


if __name__ == "__main__":
    p1 = Process(target=build_class, args=('p1',))
    p2 = Process(target=build_class, args=('p2',))
    p1.start()
    p2.start()

    p1.join()
    p2.join()

    o1 = MyClass('1')
    o2 = MyClass('2')
    print(o1)
    print(o2)
    o2.val = 'NEW'
    print(o2)


