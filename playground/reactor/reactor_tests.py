import asyncio
from multiprocessing import Process, Queue
from aioprocessing import AioQueue, AioProcess

from unittest.mock import MagicMock, call, patch
from cilantro.protocol.reactor import NetworkReactor
from cilantro.protocol.reactor.executor import *
from cilantro.messages import ReactorCommand
from unittest import TestCase
from cilantro.logger import get_logger

from cilantro.protocol.wallets import ED25519Wallet
from cilantro.messages import *

URL = 'tcp://127.0.0.1:9988'
FILTER = 'TEST_FILTER'


def thicc_test(test_cls):

    def propogate_cmd(cmd_name):
        def send_cmd(self, *args, **kwargs):
            cmd = (cmd_name, args, kwargs)
            self.cmd_q.coro_put(cmd)
        return send_cmd

    def mp_testable(cls):
        # Only copy non-internal and callable methods
        search_scope = [name for name in dir(test_cls) if
                        ((callable(getattr(test_cls, name))) and (len(name) < 2 or name[:2] != '__'))]
        for func in search_scope:
            setattr(cls, func, propogate_cmd(func))

        return cls

    return mp_testable


"""
change this so that we are not subclassing process, but rather doing some shit (maybe running a test!?) in another
proc and we ...

we need to have the creation of the reactor/server (whatever blocks) to happen in an isolated target function (a unit test?)
then, we provide a class that, like the one below, copies the funcs of reactor/server class to test, and pipes them
to a queue which gets passed into the target function of the proc
"""


@thicc_test(NetworkReactor)
class TestableReactor:
    def __init__(self):
        super().__init__()
        self.log = get_logger("TestableProcess")

        self.cmd_q = AioQueue()  # Used to pass commands into blocking object
        self.rdy_sig_q = Queue()  # Used to block on .start() and wait for child proc

        self.test_proc = Process(target=self._start_test, args=(self.rdy_sig_q, self.cmd_q))
        self.log.debug("Starting test")
        self.test_proc.start()

        # THIS DOES OUTPUT
        # self.log.critical("**tt** about to die")
        # i = 10 / 0

        self.log.debug("waiting for child ready sig")
        rdy = self.rdy_sig_q.get()
        self.log.debug("got rdy sig: {}".format(rdy))

        # THIS DOES OUTPUT
        # self.log.critical("**tt** about to die")
        # i = 10 / 0

    def _start_test(self, rdy_sig_q, cmd_q):
        async def recv_cmd():
            # WHY DOES IT NO OUT HERE?
            # HAVING OTHER TASKS IN THE LOOP SEEMS TO MAKE THIS THING BREAK..
            # log.critical("**** about to die")
            # i = 10 / 0
            # THIS DOES NOT OUTPUT ERROR!!!

            while True:
                log.critical("waiting for cmd")
                cmd = await cmd_q.coro_get()
                func, args, kwargs = cmd
                log.critical("got cmd: {}".format(cmd))
                log.critical("cmd name: {}\nkwargs: {}".format(func, kwargs))

                getattr(reactor, func)(*args, **kwargs)

        log = get_logger("TesterTarget")
        log.debug("run started")

        log.debug('sleeping')
        import time
        time.sleep(0.5)
        log.debug('yawn wake up')

        # THIS DOES OUTPUT
        # log.critical("**** about to die")
        # i = 10 / 0

        loop = asyncio.new_event_loop()
        mock_parent = MagicMock()

        # THIS DOES OUTPUT
        # log.critical("!!! about to die")
        # i = 10 / 0

        log.debug("creating reactor")
        reactor = NetworkReactor(mock_parent, loop)

        # THIS DOES NOT OUTPUT!
        # log.critical("### about to die")
        # i = 10 / 0

        log.debug("sending ready sig to parent")
        rdy_sig_q.put('ready')

        # DEBUG
        # log.critical("creating mock tester")
        # reactor.tester.do_something = MagicMock()
        # log.critical("asserting mock tester called")
        # i = 10 / 0
        # reactor.tester.do_something.assert_called()
        # log.critical("done asserting called")
        # END DEBUG

        log.debug("starting TestableProcess event loop")
        loop.run_until_complete(recv_cmd())


    def start(self):
        self.log.debug("starting...")
        super().start()
        self.log.debug("blocking...")

        msg = self.rdy_sig_q.get()
        self.log.debug("got msg: {}".format(msg))

        self.log.debug("started!")


def random_envelope():
    sk, vk = ED25519Wallet.new()
    tx = StandardTransactionBuilder.random_tx()
    return Envelope.create(signing_key=sk, sender='me', data=tx)


if __name__ == '__main__':
    log = get_logger("Main")
    log.debug("hello test")

    r1 = TestableReactor()
    # r2 = TestableReactor()

    log.critical("\n\n$$ sick bruh this doesnt block?")

    r1.add_sub(url=URL, filter=FILTER)

    # r2.add_pub(url=URL)

    import time
    time.sleep(0.2)

    # r2.pub(filter=FILTER, envelope=random_envelope())