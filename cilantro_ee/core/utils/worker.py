from cilantro_ee.core.utils.context import Context
from cilantro_ee.core.logger import get_logger
from cilantro_ee.core.sockets.socket_manager import SocketManager

from typing import Callable
import zmq.asyncio, asyncio

import uvloop
asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())


class Worker(Context):

    def __init__(self, signing_key, name=''):

        name = name or type(self).__name__
        super().__init__(signing_key=signing_key, name=name)
        self.log = get_logger(name)

        self.manager = SocketManager(context=self.zmq_ctx)
        self.tasks = self.manager.overlay_client.tasks

    async def _wait_until_ready(self):
        self.log.debugv("Started waiting for overlay server to be ready!!")
        while not self.manager.is_ready():
            await asyncio.sleep(0)
        self.log.debugv("overlay server is ready!!")


