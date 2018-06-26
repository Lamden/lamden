"""
Integration testing tools for processes with blocking event loops
"""
import asyncio, uvloop
import zmq.asyncio
import random
import inspect
import traceback
from cilantro.utils.lprocess import LProcess
from cilantro.logger import get_logger

asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())


ASSERTS_POLL_FREQ = 0.1
CHILD_PROC_TIMEOUT = 1


SIG_RDY = b'IM RDY'
SIG_SUCC = b'G00DSUCC'
SIG_FAIL = b'BADSUCC'
SIG_ABORT = b'NOSUCC'
SIG_START = b'STARTSUCC'

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


def _gen_url(name=''):
    """
    Helper method to generate a random URL for use in a PAIR socket
    """
    # TODO set host name from env vars if on VM
    HOST_NAME = '127.0.0.1'  # or node name (i.e delegate_1)
    rand_num = random.randint(0, pow(2, 16))
    return "ipc://mptest-{}-{}-{}".format(name, HOST_NAME, rand_num)


class MPTesterProcess:
    """
    We create the blocking tester object, and configure it with mock objects using a function passed in
    Then, we ensure futures __recv_cmd() to read from cmd_self.socket for proxy'd commands, and __check_assertions() to
    check assertions on a scheduled basis until they complete or until we get a SIG_ABORT from main thread
    """

    def __init__(self, name, url, build_fn, config_fn, assert_fn):
        self.url = url
        self.name = name
        self.config_fn = config_fn
        self.assert_fn = assert_fn
        self.gathered_tasks = None
        self.log = get_logger("TesterProc[{}]".format(name))

        self.tester_obj, self.loop, self.tasks = self._build_components(build_fn)

        # Connect to parent process over ipc PAIR self.socket
        self.ctx = zmq.asyncio.Context()
        self.socket = self.ctx.socket(socket_type=zmq.PAIR)
        self.socket.connect(self.url)

        if self.config_fn:
            self.tester_obj = self.config_fn(self.tester_obj)

    def start_test(self):
        """
        Sends ready signal to parent process, and then starts the event self.loop in this process
        """
        assert self.gathered_tasks is None, "start_test can only be called once"
        self.gathered_tasks = asyncio.gather(self._recv_cmd(), *self.tasks)

        self.log.debug("sending ready sig to parent")
        self.socket.send_pyobj(SIG_RDY)

        try:
            self.log.debug("starting tester proc event loop")
            self.loop.run_until_complete(self.gathered_tasks)
        except Exception as e:
            # If the tasks were canceled internally, then do not run _teardown() again
            if type(e) is asyncio.CancelledError:
                self.log.debug("Task(s) cancel detected. Closing event loop.")
                self.loop.close()
                return

            self.log.error("\n\nException in main TesterProc loop: {}\n\n".format(traceback.format_exc()))
            self.socket.send_pyobj(SIG_FAIL)
            self._teardown()

    def _build_components(self, build_fn) -> tuple:
        objs = build_fn()

        # Validate tuple
        assert type(objs) is tuple, "Expected a tuple of length 3 with (tester_obj, loop, tasks)"
        assert len(objs) == 3, "Expected a tuple of length 3 with (tester_obj, loop, tasks)"

        tester_obj, loop, tasks = objs

        # Validate loop
        assert isinstance(loop, asyncio.AbstractEventLoop), \
            "Got {} that isn't an instance of asyncio.AbstractEventLoop".format(loop)
        asyncio.set_event_loop(loop)

        # Validate tasks
        assert type(tasks) is list or type(tasks) is tuple, \
            "3rd return val of build_obj must be a list/tuple of tasks... got {} instead".format(tasks)
        # assert len(tasks) >= 1, "Expected at least one task"

        # TODO investigate why this is not always working...soemtimes assert raises error for valid coro's
        # for t in tasks:
        #     assert inspect.iscoroutine(t), "Tasks must be a list of coroutines. Element {} is not a coro.".format(t)

        return tester_obj, loop, tasks

    async def _recv_cmd(self):
        """
        Receive commands from the main process and execute them on the tester object. If cmd is equal to ABORT_SIG,
        then we execute __teardown() to stop this self.loop. If its an SIG_START, we start polling for assertions.
        Otherwise, cmd is assumed to be a a tuple of command info of the format
        (func_name: str, args: list, kwargs: dict).
        """
        while True:
            cmd = await self.socket.recv_pyobj()  # recv commands/events from test orchestrator

            # If we got a SIG_ABORT, tear this bish down
            if cmd == SIG_ABORT:
                # self.log.critical("\n!!!!!\nGOT ABORT SIG\n!!!!!\n")
                errs = self._assertions()
                if errs:
                    self.log.error("\n\n{0}\nASSERTIONS FAILED FOR {2}:\n{1}\n{0}\n".format('!' * 120, errs, self.name))
                self._teardown()
                return

            # If we got a SIG_START, start polling for assertions (if self.assert_fn passed in)
            elif cmd == SIG_START:
                self.log.debug("Got SIG_START from test orchestrator")
                if self.assert_fn:
                    self.log.debug("\nStarting to check assertions every {} seconds\n".format(ASSERTS_POLL_FREQ))
                    asyncio.ensure_future(self._check_assertions())
                continue

            # If msg is not a signal, we assume its a command tuple of form (func, args, kwargs)
            assert len(
                cmd) == 3, "Expected command tuple of len 3 with form (func: str, args: list, kwargs: dict) but " \
                           "got {}".format(cmd)
            func, args, kwargs = cmd

            # Execute cmd in a try/catch, and send a SIG_FAIL to test orchestrator proc if something blow up
            try:
                output = getattr(self.tester_obj, func)(*args, **kwargs)

                # If result is coroutine, run it in the event self.loop
                if output and inspect.iscoroutine(output):
                    self.log.debug("Coroutine detect for func name {}, running it in event self.loop".format(func))
                    result = await asyncio.ensure_future(output)
                    self.log.debug("Got result from coroutine {}\nresult: {}".format(func, result))
                # self.log.critical("got cmd: {}".format(cmd))
                # self.log.critical("cmd name: {}\nkwargs: {}".format(func, kwargs))
            except Exception as e:
                self.log.error("\n\n TESTER GOT EXCEPTION FROM EXECUTING CMD {}: {}\n\n".format(cmd, traceback.format_exc()))
                self.socket.send_pyobj(SIG_FAIL)
                self._teardown()
                return

    async def _check_assertions(self):
        """
        Schedule assertion check every TEST_CHECK_FREQ seconds, until either:
            1) The assertions exceed, in which case we send a success signal SUCC_SIG to main thread
            2) The assertions timeout, in which case we send a fail signal FAIL_SIG to main thread
            3) We get can abort cmd (read in __recv_cmd), in which case we send an ABORT_SIG to main thread

        Once one one of these conditions is met, the corresponding signal is sent to the main thread as this
        process calls __teardown() cleans up the event self.loop.
        """
        self.log.debug("Starting assertion checks")

        # Run assertions for until either case (1) or (2) described above occurs
        while True:
            if self._assertions() is None:
                break

            # Sleep until next assertion check
            await asyncio.sleep(ASSERTS_POLL_FREQ)

        # Once out of the assertion checking self.loop, send success to main thread
        self.log.debug("\n\nassertions passed! putting ready sig in queue\n\n")
        self.socket.send(SIG_SUCC)

    def _teardown(self):
        """
        Stop all tasks and close this processes event self.loop. Invoked after we successfully pass all assertions, or
        timeout.
        """
        self.log.info("Tearing down")

        self.log.debug("Closing pair socket")
        self.socket.close()

        self.log.debug("Stopping tasks")
        self.gathered_tasks.cancel()

    def _assertions(self):
        """
        Helper method to run tester object's assertions, and return the error raised as a string, or None if no
        assertions are raised
        """
        if not self.assert_fn:
            return None

        try:
            self.assert_fn(self.tester_obj)
            return None
        except Exception as e:
            return str(e)


class MPTesterBase:
    """
    TODO docstring
    """
    tester_cls = 'UNSET'

    def __init__(self, config_fn=None, assert_fn=None, name='TestableProcess', always_run_as_subproc=False, *args, **kwargs):
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
        from .mp_test_case import MPTestCase
        MPTestCase.testers.append(self)

        # Create a wrapper around the build_obj with args and kwargs. We do this b/c this function will actually be
        # invoked in a separate process/machine, thus we need to capture the function call to serialize it and send
        # it across a socket
        build_fn = wrap_func(type(self).build_obj, *args, **kwargs)

        # Create and start the subprocess that will run the blocking object
        self.test_proc = LProcess(target=self._run_test_proc, args=(self.name, self.url, build_fn,
                                                               self.config_fn, self.assert_fn,))
        self.start_test()

    def start_test(self):
        self.test_proc.start()

        self.log.debug("tester waiting for child proc rdy sig...")
        msg = self.socket.recv_pyobj()
        assert msg == SIG_RDY, "Got msg from child thread {} but expected SIG_RDY".format(msg)
        self.log.debug("GOT RDY SIG: {}".format(msg))

    def _run_test_proc(self, name, url, build_fn, config_fn, assert_fn):
        # TODO create socket outside of loop and pass it in for
        tester = MPTesterProcess(name=name, url=url, build_fn=build_fn, config_fn=config_fn, assert_fn=assert_fn)
        tester_socket = tester.socket

        try:
            tester.start_test()
        except Exception as e:
            self.log.error("\n\n TesterProcess encountered exception outside of internal loop! Error:\n {}\n\n"
                           .format(traceback.format_exc()))
            tester_socket.send_pyobj(SIG_FAIL)
            tester._teardown()

    @classmethod
    def build_obj(cls, *args, **kwargs) -> tuple:
        """
        Override to define how the blocking object should be initialized. Must return 2 element tuple, in the order
        <loop> (an EventLoop instance), and <object> (an instance of the blocking object to test).
        :return: Tuple of the form (loop, object_instance)

        It is assumed the object being returning is passed an event loop into its constructor, which it uses internally
        to schedule all its events.
        """
        raise NotImplementedError

    def teardown(self):
        self.log.debug("{} tearing down...".format(self.name))

        self.socket.close()
        self.test_proc.join()

        self.log.debug("{} done tearing down.".format(self.name))

    def __repr__(self):
        return self.name + "  " + str(type(self))
