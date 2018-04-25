from cilantro.logger import get_logger
import time
from cilantro.protocol.reactor import ReactorInterface, ReactorCore, Command
from multiprocessing import Process

URL = "tcp://127.0.0.1:5566"
URL2 = "tcp://127.0.0.1:5577"
URL3 = "tcp://127.0.0.1:5588"
URL4 = "tcp://127.0.0.1:5599"


class SlowInitNode:
    def __init__(self):
        self.log = get_logger("SlowInitNode")
        self.log.info("-- Test Node Init-ing --")
        self.reactor = ReactorInterface(self)

        self.reactor.execute(Command.ADD_SUB, url=URL, callback='do_something_else')

        self.log.critical("Starting very slow init")
        time.sleep(6)
        self.log.critical("Done with very flow init")
        self.reactor.notify_ready()

    def do_something_slow(self, data):
        self.log.critical("Starting something slow with data: {}".format(data))
        time.sleep(2)
        self.log.critical("Done with something slow for data: {}".format(data))

    def do_something_else(self, data):
        self.log.info("do_something_ELSE with data: {}".format(data))


class PubSubNode:
    def __init__(self):
        self.log = get_logger("PubSubNode")
        self.log.info("-- PubSubNode Init-ing --")

        self.reactor = ReactorInterface(self)
        self.reactor.execute(Command.ADD_SUB, url=URL, callback='do_something')
        self.reactor.execute(Command.ADD_PUB, url=URL)

        self.reactor.notify_ready()

    def do_something(self, data):
        self.log.debug("Doing something with data: {}".format(data))


def create_node():
    node = PubSubNode()
    time.sleep(2)

if __name__ == "__main__":
    log = get_logger("Main")
    log.debug("\n\n-- MAIN THREAD --")

    node1 = PubSubNode()
    node2 = PubSubNode()
    # p = Process(target=create_node)
    # p.start()
    # time.sleep(5)

    # q = aioprocessing.AioQueue()
    # reactor = ReactorInterface(queue=q)
    # reactor.start()
    #
    # q.coro_put(Command(Command.SUB, url=URL, callback=do_something))
    #
    # q.coro_put(Command(Command.PUB, url=URL2, data=b'oh boy i hope this gets through'))

