from unittest import TestCase
from pathlib import Path
import shutil

import asyncio
import uvloop
asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())

class TestNetwork(TestCase):
    def setUp(self):
        self.current_path = Path.cwd()
        self.nodes_fixtures_dir = Path(f'{self.current_path}/fixtures/nodes')

        try:
            shutil.rmtree(self.nodes_fixtures_dir)
        except:
            pass

        self.networks = []
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        self.loop.main = True

    def tearDown(self):
        self.stop_threaded_networks()

        if not self.loop.is_closed():
            self.loop.stop()
            self.loop.close()
