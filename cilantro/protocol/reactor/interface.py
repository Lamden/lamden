import asyncio
import traceback
import zmq.asyncio
from cilantro.utils import LProcess
import random
import time
from cilantro.logger import get_logger
from cilantro.messages.reactor.reactor_command import ReactorCommand
from cilantro.protocol.reactor.daemon import ReactorDaemon, CHILD_RDY_SIG, KILL_SIG
import signal, sys


class ReactorInterface:
    def __init__(self, router, loop, signing_key, name='Node'):
        self.log = get_logger("{}.ReactorInterface".format(name))
        self.url = "ipc://{}-ReactorIPC-".format(name) + str(random.randint(0, pow(2, 16)))

        # Set instance vars
        self.router = router
        self.loop = loop
        asyncio.set_event_loop(self.loop)  # not sure if we need this (we shouldnt tbh)

        # Create zmq context and pair socket to communicate with reactor sub process
        self.context = zmq.asyncio.Context()
        self.socket = self.context.socket(zmq.PAIR)

        self.socket.bind(self.url)

        # Start reactor sub process
        self.proc = LProcess(target=self._start_daemon, name='NetworkDaemon', args=(self.url, signing_key, name))
        # self.proc.daemon = True
        self.proc.start()

        self.futures = None

        # Register signal handler to teardown
        # signal.signal(signal.SIGTERM, self._signal_teardown)

        # Block execution of this proc until reactor proc is ready
        self.loop.run_until_complete(self._wait_child_rdy())

        self.torn_down = False

    def start_reactor(self, tasks):
        """
        Method to kick off the event loop and start listening to the ReactorDaemon. No callbacks from the ReactorDaemon
        are read until this method gets invoked. This blocks on whatever process its called on, and thus should be
        called AFTER any other application set up (such as starting the state machine so it enters its initial state).
        Generally speaking, this should be the last command run during application bootstrap as it blocks
        the process and opens up the system to receiving messages from ReactorDaemon (although we can still SEND msgs
        to ReactorDaemon before this method is called).

        Optionally, a list of additional tasks (asyncio Future/Task objects) can be passed in which will be included in
        the loop's run_until_complete.
        """
        try:
            self.futures = asyncio.gather(self._recv_messages(), *tasks)
            self.loop.run_until_complete(self.futures)
        except Exception as e:
            if type(e) is asyncio.CancelledError:
                self.log.warning("ReactorInterface event loop cancelled")
                return

            self.log.error("Exception in main event loop: {}".format(traceback.format_exc()))
            self.log.info("Tearing down from runtime loop exception")
            self.teardown()

    def _signal_teardown(self, signal, frame):
        self.log.fatal("Main process got kill signal: {}   ... with frame: {} ".format(signal, frame))
        self.teardown()
        sys.exit(0)

    def teardown(self):
        """
        Close sockets. Close Event Loop. Teardown. Bless up.
        """
        if not self.torn_down:
            self.torn_down = True
        else:
            return

        self.log.notice("[MAIN PROC] Tearing down Reactor Interface process (the main process)")

        self.log.info("ReactorInterface signaling teardown to daemon")
        self.socket.send(KILL_SIG)

        # Sleep to allow kill sig to be sent before closing socket
        time.sleep(2)

        if self.futures:
            self.log.debug("Canceling recv_messages future")
            self.futures.cancel()

        self.log.info("Closing pair socket")
        self.socket.close()

        self.log.info("Closing event loop")
        self.loop.call_soon_threadsafe(self.loop.stop)

    def _start_daemon(self, url, sk, name):
        """
        Should be for internal use only.
        The target method for the ReactorDaemon subprocess (this code gets run in a child process). This simply creates
        a ReactorDaemon instance, passing in the URL for the communication socket between ReactorInterface
        and ReactorDaemon. This process 'blocks' as soon as the ReactorDaemon is created.

        :param url: The url for the IPC pair socket between the ReactorInterface and ReactorDaemon
        """
        reactor = ReactorDaemon(url=url, sk=sk, name=name)

    async def _wait_child_rdy(self):
        """
        Should be for internal use only.
        Method that awaits a ready signal from the ReactorDaemon process. This is run_until_complete after we start
        the ReactorDaemon process to block execution of the main process until the ReactorDaemon sends a ready signal.
        This ensures that we do not try to send commands to the ReactorDaemon process before it is ready.
        """
        self.log.debug("Waiting for ready sig from child proc...")
        msg = await asyncio.wait_for(self.socket.recv(), 40)
        assert msg == CHILD_RDY_SIG, "Got unexpected rdy sig from child proc (got '{}', but expected '{}')" \
            .format(msg, CHILD_RDY_SIG)
        self.log.debug("Got ready sig from child proc: {}".format(msg))

    async def _recv_messages(self):
        """
        Should be for internal use only.
        Starts listening to messages from the ReactorDaemon. This method gets run_until_complete by
        invoking .start_reactor on the ReactorInterface object.
        """
        try:
            self.log.info("~~ Reactor listening to messages from ReactorDaemon ~~")
            while True:
                self.log.spam("Waiting for callback...")
                msg = await self.socket.recv()
                callback = ReactorCommand.from_bytes(msg)
                self.log.spam("Got callback cmd <{}>".format(callback))
                self.router.route_callback(callback)
        except Exception as e:
            if type(e) is asyncio.CancelledError:
                self.log.warning("ReactorInterface _recv_messages future canceled!")
            elif type(e) is zmq.error.ZMQError:
                self.log.warning("Got zmq error in ReactorInterface _recv_messages. Error = \n{}".format(e))
            else:
                raise e

    def send_cmd(self, cmd: ReactorCommand):
        assert isinstance(cmd, ReactorCommand), "Only ReactorCommand instances can sent through the reactor"
        self.socket.send(cmd.serialize())
