from cilantro_ee.protocol.comm import services
import zmq.asyncio
from cilantro_ee.protocol.wallet import Wallet
from unittest import TestCase


class TestMailbox(TestCase):
    def test_init(self):
        w = Wallet()
        services.Mailbox(services._socket('tcp://127.0.0.1:10000'), w, zmq.asyncio.Context())

