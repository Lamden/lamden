from cilantro_ee.utils.test.testnet_config import set_testnet_config
set_testnet_config('2-2-4.json')


from unittest import TestCase, mock
from unittest.mock import MagicMock
from cilantro_ee.protocol.multiprocessing.worker import Worker
from cilantro_ee.messages.base.base_signal import SignalBase
from cilantro_ee.messages.envelope.envelope import Envelope


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

    @WorkerTester.test
    def test_open_envelope_valid(self, *args):
        env_sk = 'B' * 64
        test_msg = TestMessage.create()
        env = Envelope.create_from_message(message=test_msg, signing_key=self.sk)
        env_binary = env.serialize()

        opened_env = self.worker.open_envelope(env_binary, validate=True)
        self.assertEqual(opened_env, env)

    @WorkerTester.test
    def test_open_envelope_invalid(self, *args):
        env_sk = 'B' * 64
        test_msg = TestMessage.create()
        env_binary = b'blah'

        opened_env = self.worker.open_envelope(env_binary, validate=True)
        self.assertEqual(opened_env, False)

    @WorkerTester.test
    def test_open_envelope_sender_valid(self, *args):
        env_sk = TESTNET_DELEGATES[0]['sk']
        test_msg = TestMessage.create()
        env = Envelope.create_from_message(message=test_msg, signing_key=env_sk)
        env_binary = env.serialize()

        opened_env = self.worker.open_envelope(env_binary, validate=True, sender_groups=NodeTypes.DELEGATE)
        self.assertEqual(opened_env, env)

    @WorkerTester.test
    def test_open_envelope_sender_invalid(self, *args):
        env_sk = 'ABCD' * 16
        test_msg = TestMessage.create()
        env = Envelope.create_from_message(message=test_msg, signing_key=env_sk)
        env_binary = env.serialize()

        opened_env = self.worker.open_envelope(env_binary, validate=True, sender_groups=NodeTypes.DELEGATE)
        self.assertEqual(opened_env, False)
