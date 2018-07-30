import asyncio
from multiprocessing import Queue
from aioprocessing import AioQueue
from cilantro.utils import LProcess

from unittest.mock import MagicMock, call, patch
from cilantro.protocol.reactor import ReactorInterface
from cilantro.protocol.reactor.executor import *
from cilantro.logger import get_logger

from cilantro.protocol.wallet import Wallet
from cilantro.messages.transaction.standard import StandardTransactionBuilder

URL = 'tcp://127.0.0.1:9988'
FILTER = 'TEST_FILTER'

TEST_TIMEOUT = 10
TEST_CHECK_FREQ = 0.1


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


@thicc_test(ReactorInterface)
class TestableReactor:
    def __init__(self, config_fn, assert_fn):
        super().__init__()
        self.log = get_logger("TestableProcess")

        self.config_fn = config_fn  # Function to configure object with mocks
        self.assert_fn = assert_fn  # Function to run assertions on inserted mock properties

        self.cmd_q = AioQueue()  # Used to pass commands into blocking object
        self.sig_q = Queue()  # Used to block on .start() and wait for child proc

        self.test_proc = LProcess(target=self._start_test, args=(self.sig_q, self.cmd_q))
        self.log.debug("Starting test")
        self.test_proc.start()

        self.log.debug("waiting for child ready sig")
        rdy = self.sig_q.get()
        self.log.debug("got rdy sig: {}".format(rdy))

    def _start_test(self, rdy_sig_q, cmd_q):
        async def recv_cmd():
            while True:
                log.critical("waiting for cmd")
                cmd = await cmd_q.coro_get()
                func, args, kwargs = cmd
                log.critical("got cmd: {}".format(cmd))
                log.critical("cmd name: {}\nkwargs: {}".format(func, kwargs))

                getattr(reactor, func)(*args, **kwargs)

        async def check_assertions():
            self.log.debug("Starting assertion checks")
            timeout = TEST_TIMEOUT
            while timeout > 0:
                try:
                    self.assert_fn(reactor)
                    self.log.critical("Assertions successful with {} left!".format(timeout))
                    rdy_sig_q.put("BIG TIME PLAYERS MAKE BIG TIME PLAYS")
                    break
                except Exception as e:
                    self.log.warning("assertion failed: {}".format(e))

                await asyncio.sleep(TEST_CHECK_FREQ)
                timeout -= TEST_CHECK_FREQ

        log = get_logger("TesterTarget")
        loop = asyncio.new_event_loop()
        mock_parent = MagicMock()

        log.debug("creating reactor")
        reactor = ReactorInterface(mock_parent, loop)

        log.info("setting mock config")
        reactor = self.config_fn(reactor)

        log.critical("mock property: {}".format(reactor._run_callback))

        log.debug("sending ready sig to parent")
        rdy_sig_q.put('ready')

        log.debug("starting TestableProcess event loop")
        loop.run_until_complete(asyncio.gather(recv_cmd(), check_assertions()))


def random_envelope():
    sk, vk = Wallet.new()
    tx = StandardTransactionBuilder.random_tx()
    sender = 'me'
    return Envelope.create_from_message(message=tx, signing_key=sk, sender_id=sender)


def configure_interface(reactor: ReactorInterface):
    print("\n\n configing interface \n\n")
    reactor._run_callback = MagicMock()
    return reactor


def run_assertions(reactor: ReactorInterface):
    print("\n\n running assertions on reactor._run_callback {} \n\n".format(reactor._run_callback))
    print(reactor._run_callback.assert_called())

def do_nothing(reactor: ReactorInterface):
    print("do nothing this will pass")
    pass


if __name__ == '__main__':
    log = get_logger("Main")
    log.debug("hello test")

    sub = TestableReactor(configure_interface, run_assertions)
    pub = TestableReactor(configure_interface, do_nothing)

    env = random_envelope()

    add_sub_cmd = ReactorCommand.create_cmd(SubPubExecutor.__name__, SubPubExecutor.add_sub.__name__, url=URL, filter=FILTER)
    add_pub_cmd = ReactorCommand.create_cmd(SubPubExecutor.__name__, SubPubExecutor.add_pub.__name__, url=URL)
    send_pub_cmd = ReactorCommand.create_cmd(SubPubExecutor.__name__, SubPubExecutor.send_pub.__name__, envelope=env, filter=FILTER)

    sub.send_cmd(add_sub_cmd)
    pub.send_cmd(add_pub_cmd)

    import time
    time.sleep(1)

    pub.send_cmd(send_pub_cmd)

    log.critical("waiting for kill switching from tester...")
    msg = sub.sig_q.get()
    log.critical("GOT MSG FROM TESTER PROC: {}".format(msg))