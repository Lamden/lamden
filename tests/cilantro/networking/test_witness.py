from unittest import TestCase
from unittest.mock import Mock, MagicMock
from cilantro.networking import Witness
from cilantro.networking import Masternode
import asyncio


class TestWitness(TestCase):
    def setUp(self):
        self.host = '127.0.0.1'
        self.sub_port = '9999'
        self.sub_url = 'tcp://127.0.0.1:9999'
        self.w = Witness(host=self.host, sub_port=self.sub_port)

    def test_host_and_port_storage(self):
        HOST = '127.0.0.1'
        PORT = '9999'
        w = Witness(host=self.host, sub_port=self.sub_port)
        self.assertEqual(w.host, HOST)
        self.assertEqual(w.sub_port, PORT)


class TestWitnessAsync():
    pass


class Mock_Masternode(Masternode):
    def __init__(self, number_before_kill=100000):
        self.life = number_before_kill
        super().__init__()

    def process_transaction(self, tx=None):
        self.publisher.bind(self.url)

        if self.life <= 0:
            self.publisher.send(tx)
        else:
            self.publisher.send(b'999')

        self.life -= 1
        self.publisher.unbind(self.url)

# unittest where mock masternode can send fake requests to witness

'''
def test_async(self):
    w = Witness()
    m = Mock_Masternode()
    loop = asyncio.get_event_loop()
    a = loop.create_task(m.process_transaction(tx={'hello'}))
    b= loop.create_task(w.accept_incoming_transactions())
    loop.run_until_complete([ a, b ])
'''
'''
    loop.run_until_complete([
        masternode_publish,
        witness_subscribe
    ])

    masternode sends kill transaction b'999,' b'deadbeef'

'''
