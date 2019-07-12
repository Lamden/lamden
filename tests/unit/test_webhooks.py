from unittest import TestCase
from cilantro_ee.utils.lprocess import LProcess
from cilantro_ee.nodes.masternode.webserver import *
from sanic.testing import SanicTestClient


class TestWebserver(TestCase):
    def test_start_ws(self):
        self.q = Queue()

        self.server = LProcess(target=start_webserver, name='WebServerProc', args=(self.q,))
        self.server.start()

    def test_