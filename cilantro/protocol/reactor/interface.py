import asyncio
import traceback
import zmq.asyncio
from cilantro.utils import LProcess
import random
from cilantro.logger import get_logger
from cilantro.messages import ReactorCommand
from cilantro.protocol.reactor.daemon import ReactorDaemon, CHILD_RDY_SIG
# from cilantro.protocol.transport.router import Router


class ReactorInterface:
    def __init__(self, router, loop, verifying_key, name='Node'):
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
        self.proc = LProcess(target=self._start_daemon, args=(self.url, verifying_key, name))
        self.proc.daemon = True
        self.proc.start()

        # Block execution of this proc until reactor proc is ready
        self.loop.run_until_complete(self._wait_child_rdy())

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
            self.loop.run_until_complete(asyncio.gather(self._recv_messages(), *tasks))
        except Exception as e:
            self.log.error("\n\nException in main event loop: {}\n\n".format(traceback.format_exc()))
            # TODO cancel tasks
        finally:
            self.log.critical("\nCLOSING EVENT LOOP\n")
            self.loop.close()
            self.proc.join()
            self.socket.close()

    def _start_daemon(self, url, vk, name):
        """
        Should be for internal use only.
        The target method for the ReactorDaemon subprocess (this code gets run in a child process). This simply creates
        a ReactorDaemon instance, passing in the URL for the communication socket between ReactorInterface
        and ReactorDaemon. This process 'blocks' as soon as the ReactorDaemon is created.

        :param url: The url for the IPC pair socket between the ReactorInterface and ReactorDaemon
        """
        reactor = ReactorDaemon(url=url, verifying_key=vk, name=name)

    async def _wait_child_rdy(self):
        """
        Should be for internal use only.
        Method that awaits a ready signal from the ReactorDaemon process. This is run_until_complete after we start
        the ReactorDaemon process to block execution of the main process until the ReactorDaemon sends a ready signal.
        This ensures that we do not try to send commands to the ReactorDaemon process before it is ready.
        """
        self.log.debug("Waiting for ready sig from child proc...")
        msg = await self.socket.recv()
        assert msg == CHILD_RDY_SIG, "Got unexpected rdy sig from child proc (got '{}', but expected '{}')" \
            .format(msg, CHILD_RDY_SIG)
        self.log.debug("Got ready sig from child proc: {}".format(msg))

    async def _recv_messages(self):
        """
        Should be for internal use only.
        Starts listening to messages from the ReactorDaemon. This method gets run_until_complete by
        invoking .start_reactor on the ReactorInterface object.
        """
        self.log.debug("~~ Reactor listening to messages from ReactorDaemon ~~")
        while True:
            self.log.debug("Waiting for callback...")
            msg = await self.socket.recv()
            callback = ReactorCommand.from_bytes(msg)
            self.log.debug("Got callback cmd <{}>".format(callback))

            self.router.route_callback(callback)

    def notify_resume(self):
        self.log.critical("NOTIFIY READY")
        # TODO -- implement (add queue of tx, flush on notify ready, pause on notify_pause

    def notify_pause(self):
        self.log.critical("NOTIFY PAUSE")
        # TODO -- implement

    def send_cmd(self, cmd: ReactorCommand):
        assert isinstance(cmd, ReactorCommand), "Only ReactorCommand instances can sent through the reactor"
        self.socket.send(cmd.serialize())

    def do_something(self, arg1='default'):
        self.log.critical("\n *** DOING SOMETHING with arg1 = {} *** \n".format(arg1))
