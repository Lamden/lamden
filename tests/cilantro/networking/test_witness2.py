from unittest import TestCase
from cilantro.networking import Witness2
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
    def setUp(self):
        self.host = '127.0.0.1'
        self.sub_port = '7777'
        self.pub_port = '8888'

        self.w = Witness2(sub_port=self.sub_port, pub_port=self.pub_port)

    def tearDown(self):
        """
        1) Disconnects the pub_socket that was initialized when self.mn was initalized
        2) ctx destroy closes all sockets associated with the Master node's zmq's Context
        :return:
        """
        self.w.pub_socket.disconnect(self.mn.pub_url)
        self.w.ctx.destroy()

    def test_async(self):
        pass
    #     w = Witness()
    #     m = Mock_Masternode()
    #     loop = asyncio.get_event_loop()
    #     a = loop.create_task(m.process_transaction(tx={'hello'}))
    #     b = loop.create_task(w.accept_incoming_transactions())
    #     loop.run_until_complete([ a, b ])