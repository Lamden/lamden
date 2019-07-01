from cilantro_ee.protocol.overlay.kademlia.node import Node
from cilantro_ee.constants import conf
from cilantro_ee.constants.ports import DHT_PORT
from cilantro_ee.protocol.comm import services
from cilantro_ee.protocol.wallet import Wallet

import zmq
import hashlib


def digest_from_vk(b: bytes):
    h = hashlib.sha3_256()
    h.update(b)
    return h.digest()


class RPCServer(services.RequestReplyService):
    def __init__(self, address: str, wallet: Wallet, ctx=zmq.Context):
        super().__init__(address=address, wallet=wallet, ctx=ctx)

    def handle_msg(self, msg):
        pass

class NewNetwork:
    def __init__(self, wallet, ctx:zmq.Context):
        self.wallet = wallet
        self.ctx = ctx

        self.ip = conf.HOST_IP

        # Configure node ID for DHT storage
        digest = digest_from_vk(self.wallet.verifying_key())
        self.dht_id = Node(node_id=digest,
                           ip=self.ip,
                           port=DHT_PORT,
                           vk=self.wallet.verifying_key().hex())

        # Setup reply service for Overlay requests
        self.reply_socket = self.ctx.socket(zmq.REP)
        self.reply_socket.setsockopt(zmq.LINGER, 2000)
        self.reply_socket.bind('tcp://*:{}'.format(self.port))

