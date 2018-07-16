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

TEST_PROC_SETUP_TIME = 20

MPTEST_PORT = '10200'

SIG_RDY = b'IM RDY'
SIG_SUCC = b'G00DSUCC'
SIG_FAIL = b'BADSUCC'
SIG_ABORT = b'NOSUCC'
SIG_START = b'STARTSUCC'


def wrap_func(func, *args, **kwargs):
    def _func():
        return func(*args, **kwargs)
    return _func

def mp_testable(test_cls):
    """
    Decorator to copy all the public API for object type test_cls to the decorated class. The decorated
    MPTesterBase subclass will be able to proxy commands to the 'test_cls' instance on a child process/VM via a queue.
    """
    def propogate_cmd(cmd_name):
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
    rand_num = random.randint(0, pow(2, 16))
    return "ipc://mptest-{}-{}".format(name, rand_num)


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
        self.log = get_logger("TesterProc-{}".format(name))

        self.tester_obj, self.loop, self.tasks = self._build_components(build_fn)

        # Connect to parent process over ipc PAIR self.socket
        self.ctx = zmq.asyncio.Context()
        self.socket = self.ctx.socket(socket_type=zmq.PAIR)
        self.log.info("TestProcess binding to URL {}".format(self.url))
        self.socket.bind(self.url)

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
                    self.log.critical("\n\n{0}\nASSERTIONS FAILED FOR {2}:\n{1}\n{0}\n".format('!' * 120, errs, self.name))
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
                    result = await asyncio.ensure_future(output)
            # If something blows up, teardown and send a FAIL_SIG to orchestration process
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
        self.log.debug("assertions passed! putting ready sig in queue")
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

        self.config_fn = config_fn  # Function to configure object with mocks
        self.assert_fn = assert_fn  # Function to run assertions on said mocks

        self.test_proc = None
        self.container_name = None  # Name of the docker container this object is proxying to (if run on VM)

        # Create a wrapper around the build_obj with args and kwargs. We do this b/c this function will actually be
        # invoked in a separate process/machine, thus we need to capture the function call to serialize it and send
        # it across a socket
        build_fn = wrap_func(type(self).build_obj, *args, **kwargs)

        self._config_url_and_test_proc(build_fn, always_run_as_subproc)

        # 'socket' is used to proxy commands to blocking object running in a child process (or possibly on a VM)
        self.ctx = zmq.Context()
        self.socket = self.ctx.socket(socket_type=zmq.PAIR)
        self.log.debug("Test Orchestrator connecting to url {}".format(self.url))
        self.socket.connect(self.url)

        # Block this process until we get a ready signal from the subprocess/VM
        self.wait_for_test_object()

    def _config_url_and_test_proc(self, build_fn, always_run_as_subproc):
        # Add this object to the registry of testers
        from .mp_test_case import MPTestCase
        MPTestCase.testers.append(self)

        # Create Tester object in a VM
        if MPTestCase.vmnet_test_active and not always_run_as_subproc:
            assert hasattr(MPTestCase, 'ports'), "VMNet test is active, but MPTestCase has no attribute ports"
            assert MPTestCase.ports, "VMNet test is active, but MPTestCase.ports is not set"

            name, ip = MPTestCase.next_container()
            assert name in MPTestCase.ports, "Node named {} not found in ports {}".format(name, MPTestCase.ports)
            assert MPTEST_PORT in MPTestCase.ports[name], "MPTEST_PORT {} not found in docker node {}'s ports {}"\
                                                          .format(MPTEST_PORT, name, MPTestCase.ports[name])

            url = MPTestCase.ports[name][MPTEST_PORT]  # URL the orchestration node should connect to
            url = url.replace('localhost', '127.0.0.1') # Adjust localhost to 127.0.0.1
            url = "tcp://{}".format(url)

            remote_url = "tcp://{}:{}".format(ip, MPTEST_PORT)  # URL the remote node should bind to
            # self.log.critical("ports: {}".format(MPTestCase.ports))
            self.container_name = name
            self.url = url

            runner_func = wrap_func(self._run_test_proc, self.name, remote_url, build_fn, self.config_fn, self.assert_fn)

            # TODO -- will i need a ton of imports and stuff to make this run smoothly...?
            MPTestCase.execute_python(name, runner_func, async=True)

        # Create Tester object in a Subprocess
        else:
            self.log.info("Creating Tester object in a subprocess")
            self.url = _gen_url(self.name)

            self.test_proc = LProcess(target=self._run_test_proc, args=(self.name, self.url, build_fn,
                                                                        self.config_fn, self.assert_fn,))
            self.test_proc.start()

    def wait_for_test_object(self):
        self.log.info("Tester waiting for rdy sig from test process...")
        msg = self.socket.recv_pyobj()
        assert msg == SIG_RDY, "Got msg from child thread {} but expected SIG_RDY".format(msg)
        self.log.info("GOT RDY SIG: {}".format(msg))

    @staticmethod
    def _run_test_proc(name, url, build_fn, config_fn, assert_fn):
        log = get_logger("TestObjectRunner[{}]".format(name))

        # TODO create socket outside of loop and pass it in for
        log.debug("Creating MPTesterProcess named {}...".format(name))
        tester = MPTesterProcess(name=name, url=url, build_fn=build_fn, config_fn=config_fn, assert_fn=assert_fn)
        log.debug("MPTesterProcess named {} created".format(name))
        tester_socket = tester.socket

        try:
            tester.start_test()
        except Exception as e:
            log.error("\n\n TesterProcess encountered exception outside of internal loop! Error:\n {}\n\n"
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

        if self.test_proc:
            self.log.debug("Joining tester proc {}...".format(self.name))
            self.test_proc.join()
            self.log.debug("Tester Proc {} joined".format(self.name))

        if self.container_name:
            # TODO clean up container???
            pass

        self.log.debug("{} done tearing down.".format(self.name))

    def __repr__(self):
        return '<' + self.name + "  " + str(type(self)) + '>'
