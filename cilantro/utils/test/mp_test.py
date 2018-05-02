"""
Integration testing tools for processes with blocking event loops
"""
import asyncio
import zmq.asyncio
import random
from multiprocessing import Queue
from aioprocessing import AioQueue
from cilantro.utils.lprocess import LProcess
from cilantro.logger import get_logger


TEST_TIMEOUT = 4
TEST_POLL_FREQ = 0.25


SIG_RDY = b'IM RDY'
SIG_SUCC = b'GOODSUCC'
SIG_FAIL = b'BADSUCC'
SIG_ABORT = b'NOSUCC'


CHILD_PROC_TIMEOUT = 1


# TODO -- move this thang to a better home
import os
import dill


def wrap_func(func, *args, **kwargs):
    def _func():
        return func(*args, **kwargs)
    return _func

def execute_python(node, fn, async=True, python_version='3.6'):
    fn_str = dill.dumps(fn, 0)
    exc_str = 'docker exec {} /usr/bin/python{} -c \"import dill; fn = dill.loads({}); fn();\" {}'.format(
        node,
        python_version,
        fn_str,
        '&' if async else ''
    )
    os.system(exc_str)

def something():
    from cilantro.logger import get_logger
    log = get_logger("THIS IS ON A VM")
    log.critical('\n\n\n\n\nayyyyyyyyy\n\n\n\n\n')


def mp_testable(test_cls):
    """
    Decorator to copy all the public API for object type test_cls to the decorated class. The decorated
    MPTesterBase subclass will be able to proxy commands to the 'test_cls' instance on a child process via a queue.
    """
    def propogate_cmd(cmd_name):
        """
        Sends cmd_name
        """
        def send_cmd(self, *args, **kwargs):
            cmd = (cmd_name, args, kwargs)
            self.socket.send_pyobj(cmd)
        return send_cmd

    def _mp_testable(cls):
        cls.test_cls = test_cls

        # Only copy non-internal and callable methods
        search_scope = [name for name in dir(test_cls) if
                        ((callable(getattr(test_cls, name))) and (len(name) < 2 or name[:2] != '__'))]
        for func in search_scope:
            setattr(cls, func, propogate_cmd(func))

        return cls

    return _mp_testable


def build_reactor_obj(cls) -> tuple:
    from cilantro.protocol.reactor.interface import ReactorInterface
    from unittest.mock import MagicMock

    mock_parent = MagicMock()
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    reactor = ReactorInterface(mock_parent, loop=loop)

    return reactor, loop



def _gen_url(name=''):
    """
    Helper method to generate a random URL for use in a PAIR socket
    """
    # TODO set host name from env vars if on VM
    HOST_NAME = '127.0.0.1'  # or node name (i.e delegate_1)
    rand_num = random.randint(0, pow(2, 16))
    return "ipc://mptest-{}-{}-{}".format(name, HOST_NAME, rand_num)


def start_vm_test(name, url, build_fn, config_fn, assert_fn):
    """
    Starts the test object in a subprocess.
    """
    async def __recv_cmd():
        """
        Receive commands from the main process and execute them on the tester object. If cmd is equal to ABORT_SIG,
        then we execute __teardown() to stop this loop. Otherwise, cmd is assumed to be a a tuple of command info
        of the format (func_name: str, args: list, kwargs: dict).
        """
        while True:
            cmd = await socket.recv_pyobj()

            if cmd == SIG_ABORT:
                # log.critical("\n!!!!!\nGOT ABORT SIG\n!!!!!\n")
                errs = __assertions()
                if errs:
                    log.critical("\n\n{0}\nASSERTIONS FAILED:\n{1}\n{0}\n".format('!' * 120, errs))
                __teardown()
                return

            func, args, kwargs = cmd
            getattr(tester_obj, func)(*args, **kwargs)
            # log.critical("got cmd: {}".format(cmd))
            # log.critical("cmd name: {}\nkwargs: {}".format(func, kwargs))

    async def __check_assertions():
        """
        Schedule assertion check every TEST_CHECK_FREQ seconds, until either:
            1) The assertions exceed, in which case we send a success signal SUCC_SIG to main thread
            2) The assertions timeout, in which case we send a fail signal FAIL_SIG to main thread
            3) We get can abort cmd (read in __recv_cmd), in which case we send an ABORT_SIG to main thread

        Once one one of these conditions is met, the corresponding signal is sent to the main thread as this
        process calls __teardown() cleans up the event loop.
        """
        log.debug("Starting assertion checks")

        # Run assertions for until either case (1) or (2) described above occurs
        while True:
            if __assertions() is None:
                break

            # Sleep until next assertion check
            await asyncio.sleep(TEST_POLL_FREQ)

        # Once out of the assertion checking loop, send success to main thread
        log.debug("\npassed assertions! putting ready sig in queue\n")
        socket.send(SIG_SUCC)

    def __teardown():
        """
        Stop all tasks and close this processes event loop. Invoked after we successfully pass all assertions, or
        timeout.
        """
        log.info("Tearing down")
        # log.info("Closing pair socket")
        socket.close()
        # log.info("Stopping loop")
        loop.stop()

    def __start_test():
        """
        Sends ready signal to parent process, and then starts the event loop in this process
        """
        log.debug("sending ready sig to parent")
        socket.send_pyobj(SIG_RDY)

        asyncio.ensure_future(__recv_cmd())
        if assert_fn:
            asyncio.ensure_future(__check_assertions())

        log.debug("starting tester proc event loop")
        loop.run_forever()

    def __assertions():
        """
        Helper method to run tester object's assertions, and return the error raised as a string, or None if no
        assertions are raised
        """
        if not assert_fn:
            return None

        try:
            assert_fn(tester_obj)
            return None
        except Exception as e:
            return str(e)

    # We create the blocking tester object, and configure it with mock objects using a function passed in
    # Then, we ensure futures __recv_cmd() to read from cmd_socket for proxy'd commands, and __check_assertions() to
    # check assertions on a scheduled basis until they complete or until we get a SIG_ABORT from main thread
    log = get_logger("TesterProc[{}]".format(name))

    tester_obj, loop = build_fn()
    assert isinstance(loop, asyncio.BaseEventLoop), "Got back loop that is not an instance of asyncio.BaseEventLoop"
    asyncio.set_event_loop(loop)

    # Connect to parent process over ipc PAIR socket
    ctx = zmq.asyncio.Context()
    socket = ctx.socket(socket_type=zmq.PAIR)
    socket.connect(url)

    if config_fn:
        tester_obj = config_fn(tester_obj)

    __start_test()


def _run_test_proc(name, url, build_fn, config_fn, assert_fn):
    """
    Starts the test object in a subprocess.
    """
    async def __recv_cmd():
        """
        Receive commands from the main process and execute them on the tester object. If cmd is equal to ABORT_SIG,
        then we execute __teardown() to stop this loop. Otherwise, cmd is assumed to be a a tuple of command info
        of the format (func_name: str, args: list, kwargs: dict).
        """
        while True:
            cmd = await socket.recv_pyobj()

            if cmd == SIG_ABORT:
                # log.critical("\n!!!!!\nGOT ABORT SIG\n!!!!!\n")
                errs = __assertions()
                if errs:
                    log.critical("\n\n{0}\nASSERTIONS FAILED FOR {2}:\n{1}\n{0}\n".format('!' * 120, errs, name))
                __teardown()
                return

            func, args, kwargs = cmd
            getattr(tester_obj, func)(*args, **kwargs)
            # log.critical("got cmd: {}".format(cmd))
            # log.critical("cmd name: {}\nkwargs: {}".format(func, kwargs))

    async def __check_assertions():
        """
        Schedule assertion check every TEST_CHECK_FREQ seconds, until either:
            1) The assertions exceed, in which case we send a success signal SUCC_SIG to main thread
            2) The assertions timeout, in which case we send a fail signal FAIL_SIG to main thread
            3) We get can abort cmd (read in __recv_cmd), in which case we send an ABORT_SIG to main thread

        Once one one of these conditions is met, the corresponding signal is sent to the main thread as this
        process calls __teardown() cleans up the event loop.
        """
        log.debug("Starting assertion checks")

        # Run assertions for until either case (1) or (2) described above occurs
        while True:
            if __assertions() is None:
                break

            # Sleep until next assertion check
            await asyncio.sleep(TEST_POLL_FREQ)

        # Once out of the assertion checking loop, send success to main thread
        log.debug("\n\nputting ready sig in queue\n\n")
        socket.send(SIG_SUCC)

    def __teardown():
        """
        Stop all tasks and close this processes event loop. Invoked after we successfully pass all assertions, or
        timeout.
        """
        log.info("Tearing down")
        # log.info("Closing pair socket")
        socket.close()
        # log.info("Stopping loop")
        loop.stop()

    def __start_test():
        """
        Sends ready signal to parent process, and then starts the event loop in this process
        """
        log.debug("sending ready sig to parent")
        socket.send_pyobj(SIG_RDY)

        # TODO
        # This is questionable pattern. I feel like i should be awaiting these futures not just
        # "fire and forgetting" them especially since __recv_cmd is infinite. It should be awaited until an abort sig
        # is received, or canceled if assertions pass.
        asyncio.ensure_future(__recv_cmd())
        if assert_fn:
            asyncio.ensure_future(__check_assertions())

        log.debug("starting tester proc event loop")
        loop.run_forever()

    def __assertions():
        """
        Helper method to run tester object's assertions, and return the error raised as a string, or None if no
        assertions are raised
        """
        if not assert_fn:
            return None

        try:
            assert_fn(tester_obj)
            return None
        except Exception as e:
            return str(e)

    # We create the blocking tester object, and configure it with mock objects using a function passed in
    # Then, we ensure futures __recv_cmd() to read from cmd_socket for proxy'd commands, and __check_assertions() to
    # check assertions on a scheduled basis until they complete or until we get a SIG_ABORT from main thread
    log = get_logger("TesterProc[{}]".format(name))

    tester_obj, loop = build_fn()
    assert isinstance(loop, asyncio.BaseEventLoop), "Got back loop that is not an instance of asyncio.BaseEventLoop"
    asyncio.set_event_loop(loop)

    # Connect to parent process over ipc PAIR socket
    ctx = zmq.asyncio.Context()
    socket = ctx.socket(socket_type=zmq.PAIR)
    socket.connect(url)

    if config_fn:
        tester_obj = config_fn(tester_obj)

    __start_test()
    # try:
    #     __start_test()
    #     log.critical("\n\n\n done with __start_test()\n\n")
    # except Exception as e:
    #     log.critical("\n\n\n error within __start_test().. {}\n\n".format(e))
    # finally:
    #     log.critical("\n\n finally block \n\n")


class MPTesterBase:
    """
    docstring
    """
    testers = []
    tester_cls = 'UNSET'

    def __init__(self, config_fn=None, assert_fn=None, name='TestableProcess'):
        super().__init__()
        self.log = get_logger(name)
        self.name = name
        self.url = _gen_url(name)

        self.config_fn = config_fn  # Function to configure object with mocks
        self.assert_fn = assert_fn  # Function to run assertions on said mocks

        # 'socket' is used to proxy commands to blocking object running in a child process (possibly on a VM)
        self.ctx = zmq.Context()
        self.socket = self.ctx.socket(socket_type=zmq.PAIR)
        self.socket.bind(self.url)

        # Add this object to the registry of testers
        MPTesterBase.testers.append(self)

        # Create and start the subprocess that will run the blocking object
        self.test_proc = LProcess(target=_run_test_proc, args=(self.name, self.url, type(self).build_obj,
                                                               self.config_fn, self.assert_fn,))
        self.start_test()

    def start_test(self):
        self.test_proc.start()

        # self.log.critical("\n\n attempting to execute stuff on the vm \n\n")
        # execute_python('node_8', wrap_func(start_vm_test, self.name, self.url, type(self).build_obj,
        #                                    self.config_fn, self.assert_fn), async=True)
        # execute_python('node_8', wrap_func(start_vm_test, self.name, self.url, build_reactor_obj,
        #                                    self.config_fn, self.assert_fn), async=True)
        # execute_python('node_8', wrap_func(start_vm_test), async=True)

        self.log.critical("tester waiting for child proc rdy sig...")
        msg = self.socket.recv_pyobj()
        assert msg == SIG_RDY, "Got msg from child thread {} but expected SIG_RDY".format(msg)
        self.log.critical("GOT RDY SIG: {}".format(msg))


    @classmethod
    def build_obj(cls) -> tuple:
        """
        Override to define how the blocking object should be initialized. Must return 2 element tuple, in the order
        <loop> (an EventLoop instance), and <object> (an instance of the blocking object to test).
        :return: Tuple of the form (loop, object_instance)

        It is assumed the object being returning is passed an event loop into its constructor, which it uses internally
        to schedule all its events.
        """
        raise NotImplementedError

    def teardown(self):
        # self.log.critical("\n\nTEARING DOWN\n\n")
        self.socket.close()
        # self.log.debug("---- joining {} ---".format(self.test_proc.name))
        self.test_proc.join()
        # self.log.debug("***** {} joined *****".format(self.test_proc.name))

    def __repr__(self):
        return self.name + "  " + str(type(self))


