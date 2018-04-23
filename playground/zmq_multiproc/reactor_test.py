from multiprocessing import Process
import asyncio
from cilantro.protocol.reactor import ReactorInterface, ReactorCore
from cilantro.logger import get_logger


FILTER = 'A'
FILTER2 = 'B'

URL = "tcp://127.0.0.1:5544"
URL2 = "tcp://127.0.0.1:6633"


class ReactorTest:
    def __init__(self):
        self.log = get_logger("Tester")
        self.log.info("ReactorTester created")

        self.loop = asyncio.new_event_loop()
        self.reactor = ReactorInterface(self, self.loop)

    def start(self):
        self.loop.run_forever()

    def route(self, *args, **kwargs):
        self.log.critical("ROUTE with args: {} -- kwargs: {}".format(args, kwargs))

    def route_req(self, *args, **kwargs):
        self.log.critical("ROUTE_REQ with args: {} -- kwargs: {}".format(args, kwargs))

    def route_timeout(self, *args, **kwargs):
        self.log.critical("ROUTE_TIMEOUT with args: {} -- kwargs: {}".format(args, kwargs))

    def test_blocking(self):
        self.log.critical("HELLO")


def test1():
    tester = ReactorTest()
    tester.reactor.add_pub(url=URL)
    tester.reactor.add_sub(url=URL2, msg_filter=FILTER)
    tester.start()

def test2():
    tester = ReactorTest()
    tester.reactor.add_pub(url=URL2)
    tester.reactor.add_sub(url=URL, msg_filter=FILTER)
    tester.start()


if __name__ == "__main__":
    print("main started")
    test1()
    # targets = (test1, test2)
    #
    # procs = [Process(target=tar) for tar in targets]
    #
    # for proc in procs:
    #     print("Starting proc")
    #     proc.start()

    print("Procs started")