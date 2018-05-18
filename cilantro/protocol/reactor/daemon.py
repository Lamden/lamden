import asyncio, os
import zmq.asyncio
from cilantro.logger import get_logger
from cilantro.protocol.reactor.executor import Executor
from cilantro.messages import ReactorCommand
from cilantro import Constants
from kademlia.dht import DHT
import inspect

import uvloop
import traceback
asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())

CHILD_RDY_SIG = b'ReactorDaemon Process Ready'
KILL_SIG = b'DIE'

class ReactorDHT(DHT):
    def status_update(self, *args, **kwargs):
        print('in the daemon:{}'.format(kwargs))

class ReactorDaemon:
    def __init__(self, url, verifying_key=None, name='Node'):
        self.log = get_logger("{}.ReactorDaemon".format(name))
        self.log.info("ReactorDaemon started with url {}".format(url))
        self.url = url

        # Comment out below for more granularity in debugging
        # self.log.setLevel(logging.INFO)

        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

        self.context = zmq.asyncio.Context()
        self.socket = self.context.socket(zmq.PAIR)  # For communication with main process
        self.socket.connect(self.url)

        # TODO get a workflow that runs on VM so we can test /w discovery
        self.discovery_mode = 'test' if os.getenv('TEST_NAME') else 'neighborhood'

        self.dht = ReactorDHT(node_id=verifying_key, mode=self.discovery_mode, loop=self.loop,
                       ctx=self.context, alpha=Constants.Overlay.Alpha,
                       ksize=Constants.Overlay.Ksize, max_peers=Constants.Overlay.MaxPeers, block=False)
        # log.debug('Ended up connecting to... {}'.format(self.dht.network.bootstrappableNeighbors()))

        # self.dht.set_status_update_callback(_status_update)

        # Set Executor _parent_name to differentiate between nodes in log files
        Executor._parent_name = name

        self.executors = {name: executor(self.loop, self.context, self.socket)
                          for name, executor in Executor.registry.items()}

        try:
            self.loop.run_until_complete(self._recv_messages())
        except Exception as e:
            err_msg = '\n' + '!' * 64 + '\nLoop terminating with exception:\n' + str(traceback.format_exc())
            err_msg += '\n' + '!' * 64 + '\n'
            self.log.error(err_msg)
        finally:
            # TODO -- do we need to clean up all the tasks in the loop first before we close it?
            self.loop.stop()
            self.socket.close()

    # TODO -- make a public 'send_cmd' API here that takes a ReactorCommand from the composer

    async def _recv_messages(self):
        # Notify parent proc that this proc is ready
        self.log.debug("reactorcore notifying main proc of ready")
        self.socket.send(CHILD_RDY_SIG)

        self.log.warning("-- Starting Recv on PAIR Socket at {} --".format(self.url))
        while True:
            self.log.debug("ReactorDaemon awaiting for command from main thread...")
            cmd_bin = await self.socket.recv()
            self.log.debug("Got cmd from queue: {}".format(cmd_bin))

            if cmd_bin == KILL_SIG:
                self._teardown()
                return

            # Should from_bytes be in a try/catch? I suppose if we get a bad command from the main proc we might as well
            # blow up because this is very likely because of a development error, so no try/catch for now
            cmd = ReactorCommand.from_bytes(cmd_bin)

            self._execute_cmd(cmd)

    def _teardown(self):
        """
        Close sockets. Teardown executors. Close Event Loop.
        """
        self.log.critical("Tearing down Reactor Daemon process")

        self.log.warning("Closing pair socket")
        self.socket.close()

        self.log.warning("Tearing down executors")
        for e in self.executors.values():
            e.teardown()

        self.log.warning("Closing event loop")
        self.loop.close()


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
