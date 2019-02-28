import asyncio
from cilantro_ee.logger.base import get_logger


class Test:

    def __init__(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

        self.ready = False


    async def poll_ready