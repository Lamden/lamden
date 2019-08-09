from cilantro_ee.utils.test.testnet_config import set_testnet_config
set_testnet_config('2-2-4.json')


from unittest import TestCase, mock
from unittest.mock import MagicMock
from cilantro_ee.protocol.multiprocessing.worker import Worker
from cilantro_ee.messages.base.base_signal import SignalBase


from cilantro_ee.constants.testnet import *
from cilantro_ee.nodes.base import NodeTypes


# A mock message type used just for these tests
class TestMessage(SignalBase):
    pass


class WorkerTester:

    @staticmethod
    def test(func):
        @mock.patch("cilantro_ee.protocol.multiprocessing.worker.asyncio", autospec=True)
        # @mock.patch("cilantro_ee.protocol.multiprocessing.worker.zmq", autospec=True)
        # @mock.patch("cilantro_ee.protocol.multiprocessing.worker.zmq.asyncio", autospec=True)
        @mock.patch("cilantro_ee.protocol.multiprocessing.worker.SocketManager")
        def _func(*args, **kwargs):
            return func(*args, **kwargs)
        return _func


class TestWorker(TestCase):

    @WorkerTester.test
    def setUp(self, *args):
        self.sk = 'A' * 64
        self.worker = Worker(signing_key=self.sk, name='TestWorker')

