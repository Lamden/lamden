import asyncio, os, logging
import zmq.asyncio
from cilantro.logger import get_logger
from cilantro.protocol.reactor.executor import Executor
from cilantro.messages import ReactorCommand
from cilantro import Constants
from cilantro.protocol.overlay.dht import DHT
from cilantro.protocol.structures import CappedDict
from cilantro.utils import IPUtils
from cilantro.protocol.statemachine import *
import inspect

import uvloop
import traceback
asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())

CHILD_RDY_SIG = b'ReactorDaemon Process Ready'
KILL_SIG = b'DIE'

class ReactorDaemon:
    def __init__(self, url, sk=None, name='Node'):
        self.log = get_logger("{}.ReactorDaemon".format(name))
        self.log.info("ReactorDaemon started with url {}".format(url))
        self.url = url

        # Comment out below for more granularity in debugging
        self.log.setLevel(logging.INFO)

        # TODO optimize cache
        self.ip_cache = CappedDict(max_size=64)

        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

        # TODO get a workflow that runs on VM so we can test /w discovery
        self.discovery_mode = 'test' if os.getenv('TEST_NAME') else 'neighborhood'
        self.dht = DHT(sk=sk, mode=self.discovery_mode, loop=self.loop,
                       alpha=Constants.Overlay.Alpha, ksize=Constants.Overlay.Ksize,
                       max_peers=Constants.Overlay.MaxPeers, block=False, cmd_cli=False, wipe_certs=True)

        self.log.debug('bootstrappable neighbors: {}'.format(self.dht.network.bootstrappableNeighbors()))

        # self.context = zmq.asyncio.Context()
        self.context, auth = self.dht.network.ironhouse.secure_context(async=True)
        self.dht.network.ironhouse.daemon_auth = auth
        self.socket = self.context.socket(zmq.PAIR)  # For communication with main process
        self.socket.connect(self.url)

        # Set Executor _parent_name to differentiate between nodes in log files
        Executor._parent_name = name

        self.executors = {name: executor(self.loop, self.context, self.socket, self.dht.network.ironhouse)
                          for name, executor in Executor.registry.items()}

        try:
            self.loop.run_until_complete(self._recv_messages())
        except Exception as e:
            err_msg = '\n' + '!' * 64 + '\nDeamon Loop terminating with exception:\n' + str(traceback.format_exc())
            err_msg += '\n' + '!' * 64 + '\n'
            self.log.error(err_msg)
            self._teardown()

    async def _recv_messages(self):
        # Notify parent proc that this proc is ready
        self.log.debug("reactorcore notifying main proc of ready")
        self.socket.send(CHILD_RDY_SIG)

        self.log.info("-- Daemon proc listening to main proc on PAIR Socket at {} --".format(self.url))
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

            # DEBUG LINE, REMOVE LATER
            # self.log.critical("got cmd from ReactorInterfac pair socket {}".format(cmd))

            assert cmd.class_name and cmd.func_name, "Received invalid command with no class/func name!"

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
        self.loop.stop()

    def _execute_cmd(self, cmd: ReactorCommand):
        """
        Propagates a command to the appropriate executor
        :param cmd: an instance of ReactorCommand
        """
        assert isinstance(cmd, ReactorCommand), "Cannot execute cmd {} that is not a ReactorCommand object".format(cmd)

        cmd_args = self._parse_cmd(cmd)
        if cmd_args:
            executor_name, executor_func, kwargs = cmd_args
        else:
            self.log.debug('Command requires VK lookup. Short circuiting from _execute_cmd.')
            return

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
        del kwargs['class_name']
        del kwargs['func_name']

        # Add envelope to kwargs if its in the reactor command
        if cmd.envelope_binary:
            kwargs['envelope'] = cmd.envelope_binary

        # Replace VK with IP address if necessary
        if 'url' in kwargs:
            self.log.debug("Processing command with url {}".format(kwargs['url']))
            url = kwargs['url']

            # Check if URL has a VK inside
            vk = IPUtils.get_vk(url)
            if vk:
                if vk == self.dht.network.ironhouse.vk:
                    ip = self.dht.ip
                else:
                    ip = self.dht.network.lookup_ip_in_cache(vk)
                if not ip:
                    self.log.info("Could not find ip for vk {} in cache. Performing lookup in DHT.".format(vk))

                    asyncio.ensure_future(self._lookup_ip(cmd, url, vk))
                    return

                new_url = IPUtils.interpolate_url(url, ip)
                kwargs['url'] = new_url

        return executor_name, executor_func, kwargs

    async def _lookup_ip(self, cmd, url, vk, *args, **kwargs):
        ip = None
        try:
            ip = await self.dht.network.lookup_ip(vk)
        except Exception as e:
            delim_line = '!' * 64
            err_msg = '\n\n' + delim_line + '\n' + delim_line
            err_msg += '\n ERROR CAUGHT IN LOOKUP FUNCTION {}\ncalled \w args={}\nand kwargs={}\n'\
                        .format(args, kwargs)
            err_msg += '\nError Message: '
            err_msg += '\n\n{}'.format(traceback.format_exc())
            err_msg += '\n' + delim_line + '\n' + delim_line
            self.log.error(err_msg)

        if ip is None:

            kwargs = cmd.kwargs
            callback = ReactorCommand.create_callback(callback=StateInput.LOOKUP_FAILED, **kwargs)
            self.log.debug("Sending callback failure to mainthread {}".format(callback))
            self.socket.send(callback.serialize())
            # TODO -- send callback to SM saying hey i couldnt lookup this vk

            return

        # Send interpolated command back through pipeline
        new_url = IPUtils.interpolate_url(url, ip)
        kwargs = cmd.kwargs
        kwargs['url'] = new_url
        new_cmd = ReactorCommand.create_cmd(envelope=cmd.envelope, **kwargs)

        self._execute_cmd(new_cmd)
