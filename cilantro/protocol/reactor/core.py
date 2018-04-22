import asyncio
from cilantro.logger import get_logger
from cilantro.protocol.reactor.executor import *
from cilantro.messages import ReactorCommand

CHILD_RDY_SIG = b'HI ITS ME CHILD PROC, LETS DO THIS MY GUY'


class ReactorCore:
    def __init__(self, url, p_name=''):
        self.log = get_logger("{}.ReactorCore".format(p_name))
        self.log.info("ReactorCore started with url {}".format(url))
        self.url = url

        # DEBUG LINE TODO remove this
        # THIS OUTPUTS
        # self.log.critical("CHECK 1 REACTOR CORE SELF DESTRUCT")
        # i = 10 / 0

        # Comment out below for more granularity in debugging
        # self.log.setLevel(logging.INFO)

        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        self.context = zmq.asyncio.Context()
        self.socket = self.context.socket(zmq.PAIR)
        self.socket.connect(self.url)

        # DEBUG LINE TODO remove this
        # THIS OUTPUTS
        # self.log.critical("CHECK 2 REACTOR CORE SELF DESTRUCT")
        # i = 10 / 0

        self.executors = {name: executor(self.loop, self.context, self.socket)
                          for name, executor in Executor.registry.items()}

        self.loop.run_until_complete(self._recv_messages())

        # DEBUG LINE TODO remove this
        # THIS NEVER RUNS (we block above)
        self.log.critical("CHECK 3 REACTOR CORE SELF DESTRUCT")
        i = 10 / 0

    async def _recv_messages(self):
        # Notify parent proc that this proc is ready
        self.log.debug("reactorcore notifying main proc of ready")
        self.socket.send(CHILD_RDY_SIG)

        self.log.warning("-- Starting Recv on PAIR Socket at {} --".format(self.url))
        while True:
            self.log.debug("Reading socket...")
            cmd_bin = await self.socket.recv()
            self.log.debug("Got cmd from queue: {}".format(cmd_bin))

            # TODO -- context managers to pretty this up
            try:
                cmd = ReactorCommand.from_bytes(cmd_bin)
            except Exception as e:
                self.log.error("Error deserializing ReactorCommand: {}\n with command binary: {}".format(e, cmd_bin))
                return

            self.execute_cmd(cmd)

    def execute_cmd(self, cmd):
        assert isinstance(cmd, ReactorCommand), "Cannot execute cmd {} that is not a ReactorCommand object".format(cmd)
        self.log.debug("Executing cmd: {}".format(cmd))

        executor_name = cmd.class_name
        executor_func = cmd.func_name
        kwargs = cmd.kwargs

        if cmd.data:
            kwargs['data'] = cmd.data
        if cmd.metadata:
            kwargs['metadata'] = cmd.metadata

        assert executor_name in self.executors, "Executor name {} not found in executors {}"\
            .format(executor_name, self.executors)
        assert hasattr(self.executors[executor_name], executor_func), "Function {} not found on executor class {}"\
            .format(executor_func, self.executors[executor_name])

        # Execute command
        getattr(self.executors[executor_name], executor_func)(**kwargs)