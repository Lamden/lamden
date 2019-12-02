# Start Authenticator (once we figure it out)
# Start Overlay Server / Discover
# Run Catchup
# Start Rocks?
# Start Mongo?

from cilantro_ee.services.storage.vkbook import VKBook
from cilantro_ee.services.storage.state import MetaDataStorage
from cilantro_ee.services.overlay.network import Network
from cilantro_ee.core.crypto.wallet import Wallet
import zmq.asyncio

'''
peer_service_port: int=DHT_PORT,
event_publisher_port: int=EVENT_PORT,
discovery_port: int=DISCOVERY_PORT,
ctx=zmq.asyncio.Context(),
ip=conf.HOST_IP,
bootnodes=conf.BOOT_DELEGATE_IP_LIST + conf.BOOT_MASTERNODE_IP_LIST,
initial_mn_quorum=1,
initial_del_quorum=1,
mn_to_find=[],
del_to_find=[]):
'''

class Node:
    def __init__(self, wallet: Wallet, ip: str, ctx: zmq.asyncio.Context(), state: MetaDataStorage, bootnodes):
        self.wallet = wallet
        self.ctx = ctx
        self.state = state
        self.bootnodes = bootnodes
        self.ip = ip

        self.network = Network(peer_service_port=10001, event_publisher_port=10002, discovery_port=10003,
                               ctx=self.ctx, ip=self.ip, bootnodes=bootnodes)

    async def start(self):
        pass