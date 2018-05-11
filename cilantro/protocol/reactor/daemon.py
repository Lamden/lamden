import asyncio, os
import zmq.asyncio
from cilantro.logger import get_logger
from cilantro.protocol.reactor.executor import Executor
from cilantro.messages import ReactorCommand
from cilantro.protocol.networks import Discovery


from kademlia.network import Server


CHILD_RDY_SIG = b'ReactorDaemon Process Ready'


class ReactorDaemon:
    def __init__(self, url, p_name=''):
        self.log = get_logger("{}.ReactorDaemon".format(p_name))
        self.log.info("ReactorDaemon started with url {}".format(url))
        self.url = url

        # Comment out below for more granularity in debugging
        # self.log.setLevel(logging.INFO)

        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

        self.context = zmq.asyncio.Context()
        self.socket = self.context.socket(zmq.PAIR)  # For communication with main process
        self.socket.connect(self.url)

        self.executors = {name: executor(self.loop, self.context, self.socket)
                          for name, executor in Executor.registry.items()}

        # Start discovery service
        # self.discoverer = Discovery(self.context)

        # self.log.info("Starting discovery sweep")
        # cilantro_ips = self.discoverer.discover('test' if os.getenv('TEST_NAME') else 'neighborhood')
        # self.log.info("Discovery sweep finished with ips: {}".format(cilantro_ips))

        # TODO bootstrap overlay network with cilantro IPss

        # Start listening to main thread as well as outside discovery pings
        # self.loop.run_until_complete(asyncio.gather(self._recv_messages(), self.discoverer.listen_for_crawlers()))
        self.loop.run_until_complete(self._recv_messages())

    async def _recv_messages(self):
        # Notify parent proc that this proc is ready
        self.log.debug("reactorcore notifying main proc of ready")
        self.socket.send(CHILD_RDY_SIG)

        self.log.warning("-- Starting Recv on PAIR Socket at {} --".format(self.url))
        while True:
            self.log.debug("ReactorDaemon awaiting for command from main thread...")
            cmd_bin = await self.socket.recv()
            # self.log.debug("Got cmd from queue: {}".format(cmd_bin))

            # Should from_bytes be in a try/catch? I suppose if we get a bad command from the main proc we might as well
            # blow up because this is very likely because of a development error, so no try/catch for now
            cmd = ReactorCommand.from_bytes(cmd_bin)
            self._execute_cmd(cmd)

    def _execute_cmd(self, cmd: ReactorCommand):
        """
        Propagates a command to the appropriate executor
        :param cmd: an instance of ReactorCommand
        """
        assert isinstance(cmd, ReactorCommand), "Cannot execute cmd {} that is not a ReactorCommand object".format(cmd)

        self.log.debug("Executing cmd {}".format(cmd))

        executor_name, executor_func, kwargs = self._parse_cmd(cmd)

        # Sanity checks (for catching bugs mostly)
        assert executor_name in self.executors, "Executor name {} not found in executors {}"\
            .format(executor_name, self.executors)
        assert hasattr(self.executors[executor_name], executor_func), "Function {} not found on executor class {}"\
            .format(executor_func, self.executors[executor_name])

        # Execute command
        getattr(self.executors[executor_name], executor_func)(**kwargs)

    def _parse_cmd(self, cmd: ReactorCommand):
        """
        Parses a cmd for execution, by extracting/preparing the necessary kwargs for execution.
        :param cmd: an instance of ReactorCommand
        :return: A tuple of 3 elements (executor_name, executor_func, kwargs)
        """
        executor_name = cmd.class_name
        executor_func = cmd.func_name
        kwargs = cmd.kwargs

        # Remove class_name and func_name from kwargs. We just need these to lookup the function to call
        del(kwargs['class_name'])
        del(kwargs['func_name'])

        # Add envelope to kwargs if its in the reactor command
        if cmd.envelope_binary:
            kwargs['envelope'] = cmd.envelope_binary

        # Lookup 'node_id' (which is a verifying key), and set lookup the corresponding IP and set that to URL
        # if necessary
        # assert either (url XOR node_vk) or both don't exist in kwargs
        # if noke_vk is in there, lookup to appropriate url
        # how to handle ports now? should we just have set ports for all the grouping????
        # TODO -- implement this functionality

        return executor_name, executor_func, kwargs



