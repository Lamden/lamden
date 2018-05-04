import asyncio
import zmq.asyncio
from cilantro.logger import get_logger
from cilantro.protocol.reactor.executor import Executor
from cilantro.messages import ReactorCommand


CHILD_RDY_SIG = b'ReactorCore Process Ready'


class ReactorCore:
    def __init__(self, url, p_name=''):
        self.log = get_logger("{}.ReactorCore".format(p_name))
        self.log.info("ReactorCore started with url {}".format(url))
        self.url = url

        # Comment out below for more granularity in debugging
        # self.log.setLevel(logging.INFO)

        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        self.context = zmq.asyncio.Context()
        self.socket = self.context.socket(zmq.PAIR)
        self.socket.connect(self.url)

        self.executors = {name: executor(self.loop, self.context, self.socket)
                          for name, executor in Executor.registry.items()}

        self.loop.run_until_complete(self._recv_messages())

    async def _recv_messages(self):
        # Notify parent proc that this proc is ready
        self.log.debug("reactorcore notifying main proc of ready")
        self.socket.send(CHILD_RDY_SIG)

        self.log.warning("-- Starting Recv on PAIR Socket at {} --".format(self.url))
        while True:
            self.log.debug("ReactorCore awaiting for command from main thread...")
            cmd_bin = await self.socket.recv()
            # self.log.debug("Got cmd from queue: {}".format(cmd_bin))

            # Should this be in a try catch? I suppose if we get a bad command from the main proc we might as well
            # blow up because this is very likely because of a development error, so no try/catch for now
            cmd = ReactorCommand.from_bytes(cmd_bin)
            self.execute_cmd(cmd)

    def execute_cmd(self, cmd: ReactorCommand):
        assert isinstance(cmd, ReactorCommand), "Cannot execute cmd {} that is not a ReactorCommand object".format(cmd)
        # self.log.debug("Executing cmd {}".format(cmd))

        executor_name = cmd.class_name
        executor_func = cmd.func_name
        kwargs = cmd.kwargs

        # Remove class_name and func_name from kwargs
        del(kwargs['class_name'])
        del(kwargs['func_name'])

        if cmd.envelope_binary:
            kwargs['envelope'] = cmd.envelope_binary

        # Validate Command (for debugging mostly)
        assert executor_name in self.executors, "Executor name {} not found in executors {}"\
            .format(executor_name, self.executors)
        assert hasattr(self.executors[executor_name], executor_func), "Function {} not found on executor class {}"\
            .format(executor_func, self.executors[executor_name])

        # Execute command
        getattr(self.executors[executor_name], executor_func)(**kwargs)
