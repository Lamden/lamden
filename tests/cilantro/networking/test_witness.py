from unittest import TestCase
from unittest.mock import Mock, MagicMock
from cilantro.networking import Witness
from cilantro.networking import Masternode
import asyncio
class Mock_Masternode(Masternode):
    def __init__(self, number_before_kill=10):
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

class TestWitness(TestCase):
    def test_async(self):
        w = Witness()
        m = Mock_Masternode()
        loop = asyncio.get_event_loop()
        a = loop.create_task(m.process_transaction(tx={'hello'}))
        b = loop.create_task(w.accept_incoming_transactions())
        loop.run_until_complete([ a, b ])



# unittest where mock masternode can send fake requests to witness



'''
    loop.run_until_complete([
        masternode_publish,
        witness_subscribe
    ])
    
    masternode sends kill transaction b'999,' b'deadbeef'
    
'''
