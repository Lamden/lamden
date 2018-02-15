from unittest import TestCase
from cilantro.networking import Witness2
from cilantro.proofs.pow import SHA3POW, POW
from cilantro.networking import Masternode
import asyncio
import requests

# class Mock_Masternode(Masternode):
#     def __init__(self, number_before_kill=10):
#         self.life = number_before_kill
#         super().__init__()
#
#     def process_transaction(self, tx=None):
#         self.publisher.bind(self.url)
#
#         if self.life <= 0:
#             self.publisher.send(tx)
#         else:
#             self.publisher.send(b'999')
#
#         self.life -= 1
#         self.publisher.unbind(self.url)


class TestWitness(TestCase):
    def setUp(self):
        self.host = '127.0.0.1'
        self.sub_port = '8888'
        self.pub_port = '8080'
        self.hasher = SHA3POW
        self.w = Witness2(sub_port=self.sub_port, pub_port=self.pub_port, hasher=POW)

    def tearDown(self):
        """
        1) Disconnects the pub_socket that was initialized when self.mn was initalized
        2) ctx destroy closes all sockets associated with the Master node's zmq's Context
        """
        self.w.pub_socket.disconnect(self.w.pub_url)
        self.w.ctx.destroy()

    def test_hasher(self):
        """
        Tests if the witness hasher is either POW or SHA3POW
        :return:
        """
        witness_hasher = self.w.hasher
        self.assertTrue(SHA3POW or POW, witness_hasher)

    def test_subscribing(self):
        # self.w.start_subscribing()
        pass

    def test_handle_req(self):
        pass

    def test_handle_req_hasher_check(self):
        """
        Tests that an error is thrown due to hasher.check
        """
        pass

    def test_async(self):
        # m = Masternode(external_port='7777', internal_port='8888')
        # self.w.start_async()
        # m.setup_web_server()
        # data = {"payload": {"to": "kevin", "amount": "900", "from": "davis", "type": "t"}, "metadata": {"sig": "0x123", "proof": "000000"}}
        # r = requests.post(url="127.0.0.1:7777", data=data)
        # print(r.status_code)
        # print(r.)
        pass

