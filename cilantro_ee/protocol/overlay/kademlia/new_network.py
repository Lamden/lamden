from cilantro_ee.constants import conf
from cilantro_ee.constants.ports import DHT_PORT, DISCOVERY_PORT
from cilantro_ee.constants.overlay_network import PEPPER
from cilantro_ee.protocol.overlay.kademlia import discovery
from cilantro_ee.protocol.comm import services
from cilantro_ee.protocol.wallet import Wallet

import asyncio
import json
import zmq
from cilantro_ee.logger.base import get_logger

log = get_logger('NetworkService')


def ip_string_from_bytes(b: bytes):
    b = bytearray(b)
    ip = [str(byte) for byte in b[0:4]]
    ip = '.'.join(ip)
    return ip


def bytes_from_ip_string(ip: str):
    b = ip.split('.')
    return bytes(b)


class KTable:
    def __init__(self, data: dict, initial_peers={}, response_size=10):
        self.data = data
        self.peers = initial_peers
        self.response_size = response_size

    def find(self, key):
        if key in self.data:
            return self.data
        elif key in self.peers:
            return {
                key: self.peers[key]
            }
        else:
            # Do an XOR sort on all the keys to find neighbors
            closest_peer_keys = sorted(self.peers.items(), key=lambda k: key ^ k)

            # Only keep the response size number
            closest_peer_keys = closest_peer_keys[:self.response_size]

            # Dict comprehension
            neighbors = {k: self.peers[k] for k in closest_peer_keys}

            return neighbors


class RPCServer(services.RequestReplyService):
    def __init__(self, address: str, event_address: str, wallet: Wallet, ctx=zmq.Context):
        super().__init__(address=address, wallet=wallet, ctx=ctx)

        self.is_connected = False
        self.wallet = wallet

        data = {
            self.wallet.verifying_key(): bytes_from_ip_string(conf.HOST_IP)
        }
        self.table = KTable(data=data)

    def handle_msg(self, msg):
        # Ping messages are empty and will eventually replace discovery
        if len(msg) == 0:
            return b''
        elif len(msg) == 32:
            # Try to find the key value
            # Result will be a dictionary.
            return self.table.find(msg)

        elif len(msg) == 32 + 4:
            asyncio.ensure_future(self.handle_join(msg))

    async def handle_join(self, msg):
        vk = msg[:32]
        ip = msg[32:]

        result = self.table.find(vk)

        if vk not in result or result[vk] != ip:
            # Ping discovery server
            ip_string = ip_string_from_bytes(ip)
            address = 'tcp://{}:{}'.format(ip_string, DISCOVERY_PORT)
            _, responded_vk = await discovery.ping(address, pepper=PEPPER, timeout=1000)

            if responded_vk == vk:
                # Valid response
                self.table.peers[vk] = ip
