import asyncio
import zmq.asyncio
from unittest.mock import MagicMock, call, patch
from cilantro.messages import *
from cilantro.protocol.wallets import ED25519Wallet
from cilantro.protocol.reactor import ReactorInterface
from cilantro.protocol.reactor.core import CHILD_RDY_SIG
from cilantro.protocol.reactor.executor import *
from cilantro.messages import ReactorCommand
from unittest import TestCase
from multiprocessing import Queue
from aioprocessing import AioQueue
from cilantro.utils import LProcess
import time

URL = 'tcp://127.0.0.1:9988'
FILTER = 'TEST_FILTER'

TEST_TIMEOUT = 8
TEST_CHECK_FREQ = 0.5

SUCC_SIG = 'GOODSUCC'
FAIL_SIG = 'BADSUCC'


def thicc_test(test_cls):
    """
    Decorator to copy all the public API for object type test_cls to the decorated class. The decorated
    class will be able to issue commands to the 'test_cls' on a child proc via a simple queue.
    """
    def propogate_cmd(cmd_name):
        """
        Sends cmd_name
        """
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

class TTBase:
    def __init(self, config_fn, assert_fn, name='TestableProcess'):
        super().__init__()
        self.log = get_logger(name)
        self.name = name

        self.config_fn = config_fn  # Function to configure object with mocks
        self.assert_fn = assert_fn  # Function to run assertions on inserted mock properties

        self.cmd_q = AioQueue()  # Used to pass commands into blocking object
        self.sig_q = Queue()  # Used to block on .start() and wait for child proc

        self.test_proc = LProcess(target=self._start_test, args=(self.sig_q, self.cmd_q))
        self.log.debug("Starting test")

    def _start_proc(self):
        """
        Starts the process in a subprocess.
        :return:
        """
        pass

    def _wait_child_rdy(self):
        pass

    def teardown(self):
        self.log.critical("\n\nTEARING DOWN\n\n")
        self.log.info("\n ---- joining --- \n")
        self.test_proc.join()
        self.log.info("\n ***** JOINED ***** \n")




@thicc_test(ReactorInterface)
class TestableReactor:
    def __init__(self, config_fn, assert_fn, name='TestableProcess'):
        super().__init__()
        self.log = get_logger(name)
        self.name = name

        self.config_fn = config_fn  # Function to configure object with mocks
        self.assert_fn = assert_fn  # Function to run assertions on inserted mock properties

        # 'cmd_q' is used to pass commands into blocking object
        # We use AioQueue here because we want to hook it into the blocking object's event loop
        self.cmd_q = AioQueue()

        # 'sig_q' is used to block on .start() and wait for child proc, as well as to send signals to main proc
        # We use multiprocessing.Queue here because we want it to block
        self.sig_q = Queue()

        # Create the subprocess that will run the blocking object
        self.test_proc = LProcess(target=self._start_test, args=(self.sig_q, self.cmd_q))
        self.log.debug("Starting test")
        self.test_proc.start()

        # Block until test_proc is ready
        self.log.debug("waiting for child ready sig")
        rdy = self.sig_q.get()
        self.log.debug("got rdy sig: {}".format(rdy))

    def wait_finish(self):
        # Block until test_proc returns from testing (success or timeout)
        self.log.critical("\n ** STARTING TEST UNTIL TERMINATION ** \n")
        msg = self.sig_q.get()
        self.log.critical("!!!!\ngot termination signal: {}\n".format(msg))

        # Teardown
        self.teardown()

        # Raise exception so test will fail if we got a fail sig
        if msg == FAIL_SIG:
            raise Exception("Tests timed out for reactor {}".format(self.name))

    def teardown(self):
        self.log.critical("\nTEARING DOWN\n")
        self.log.info("\n ---- joining --- \n")
        self.test_proc.join()
        self.log.info("\n ***** JOINED ***** \n")

    def build_obj(self):
        self.log.critical("BUILDING OBJECT!")

        mock_parent = MagicMock()
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        self.log.debug("creating reactor")
        reactor = ReactorInterface(mock_parent, loop)

        return reactor, mock_parent, loop

    def _start_test(self, rdy_sig_q, cmd_q):
        def teardown():
            log.critical("\nsubproc tearing down\n")
            loop.run_until_complete(loop.shutdown_asyncgens())
            log.critical("\nstopping loop\n")
            loop.stop()
            log.critical("\nclosing loop\n")
            loop.close()

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
                    padding = '#' * 120
                    self.log.critical("\n{0}\n{0}\nAssertions successful with {1} seconds left!\n{0}\n{0}\n"
                                      .format(padding, timeout))
                    break
                except Exception as e:
                    log.warning("assertion failed: {}".format(e))

                await asyncio.sleep(TEST_CHECK_FREQ)
                timeout -= TEST_CHECK_FREQ

            if timeout > 0:
                print("\n\nputting ready sig in queue\n\n")
                rdy_sig_q.put(SUCC_SIG)
            else:
                print("\n\nputting timeout\n\n")
                rdy_sig_q.put(FAIL_SIG)

            teardown()
            self.log.critical("done teardown inside check_assertions")

        log = get_logger("TesterTarget")
        # mock_parent = MagicMock()
        #
        # loop = asyncio.new_event_loop()
        # asyncio.set_event_loop(loop)
        #
        # log.debug("creating reactor")
        # reactor = ReactorInterface(mock_parent, loop)
        reactor, mock_parent, loop = self.build_obj()

        log.info("setting mock config")
        reactor = self.config_fn(reactor)

        log.critical("mock property: {}".format(reactor._run_callback))

        log.debug("sending ready sig to parent")
        rdy_sig_q.put('ready')

        log.debug("starting TestableProcess event loop")
        # loop.run_until_complete(asyncio.gather(recv_cmd(), check_assertions()))
        asyncio.ensure_future(recv_cmd())
        asyncio.ensure_future(check_assertions())
        loop.run_forever()

def AsyncMock(*args, **kwargs):
    m = MagicMock(*args, **kwargs)

    async def mock_coro(*args, **kwargs):
        return m(*args, **kwargs)

    mock_coro.mock = m
    return mock_coro


class IntegrationTestReactor(TestCase):

    @classmethod
    def random_envelope(cls):
        sk, vk = ED25519Wallet.new()
        tx = StandardTransactionBuilder.random_tx()
        sender = 'me'
        return Envelope.create_from_message(message=tx, signing_key=sk, sender_id=sender)

    def test_subpub_1(self):
        """
        Tests sub/pub 1-1 with one message
        """
        def configure_interface(reactor: ReactorInterface):
            print("\nconfiguring interface\n")
            reactor._run_callback = MagicMock()
            return reactor

        def run_assertions(reactor: ReactorInterface):
            print("\nrunning assertions on reactor._run_callback {}\n".format(reactor._run_callback))
            callback = 'route'
            reactor._run_callback.assert_called_with(callback, env.serialize())

        def do_nothing(reactor: ReactorInterface):
            print("do_nothing so this should immediately pass")
            if not hasattr(reactor, '_timer'):
                reactor._timer = 4

            if reactor._timer > 0:
                reactor._timer -= TEST_CHECK_FREQ
                raise Exception("still {} seconds left on dummy assertions".format(reactor._timer))

            # raise Exception("lol get rekt")

        log = get_logger("TestSubPub1")

        env = IntegrationTestReactor.random_envelope()

        sub = TestableReactor(configure_interface, run_assertions, name='** SUB')
        pub = TestableReactor(configure_interface, do_nothing, name='++ PUB')

        add_sub_cmd = ReactorCommand.create_cmd(SubPubExecutor.__name__, SubPubExecutor.add_sub.__name__, url=URL,
                                                filter=FILTER)
        add_pub_cmd = ReactorCommand.create_cmd(SubPubExecutor.__name__, SubPubExecutor.add_pub.__name__, url=URL)
        send_pub_cmd = ReactorCommand.create_cmd(SubPubExecutor.__name__, SubPubExecutor.send_pub.__name__,
                                                 envelope=env, filter=FILTER)

        sub.send_cmd(add_sub_cmd)
        pub.send_cmd(add_pub_cmd)
        time.sleep(0.2)
        pub.send_cmd(send_pub_cmd)

        # Blocks until they finish
        log.critical("\n\nSTARTING SUB TEST\n\n")
        sub.wait_finish()
        log.critical("\n\nSTARTING PUB TEST\n\n")
        pub.wait_finish()

    #
    # def test_subpub_2(self):
    #     """
    #     Tests sub/pub 1-3 with one message
    #     """
    #     def configure_interface(reactor: ReactorInterface):
    #         pass
    #     pass






















