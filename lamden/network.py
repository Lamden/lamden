import time
import hashlib
import asyncio
import os
import zmq.asyncio
from contracting.db.encoder import encode

from lamden.formatting import rules, primatives
from lamden.crypto.wallet import Wallet, verify
from lamden import router
from lamden.logger.base import get_logger

PROOF_EXPIRY = 15
PEPPER = 'cilantroV1'
LOGGER = get_logger('Network')

JOIN_SERVICE = 'join'           # Unsecured
IDENTITY_SERVICE = 'identity'   # Unsecured
PEER_SERVICE = 'peers'


def verify_proof(proof, pepper):
    # Proofs expire after a minute
    if not primatives.check_format(proof, rules.PROOF_MESSAGE_RULES):
        return False

    if int(time.time()) - proof['timestamp'] > PROOF_EXPIRY:
        return False

    message = [pepper, proof['ip'], proof['timestamp']]
    message_bytes = encode(message).encode()

    h = hashlib.sha3_256()
    h.update(message_bytes)

    return verify(proof['vk'], h.digest().hex(), proof['signature'])


class IdentityProcessor(router.Processor):
    def __init__(self, wallet: Wallet, ip_string: str, pepper: str=PEPPER):
        self.pepper = pepper
        self.wallet = wallet
        self.ip_string = ip_string

    async def process_message(self, msg):
        return self.create_proof()

    def create_proof(self):
        now = int(time.time())
        message = [self.pepper, self.ip_string, now]

        message_bytes = encode(message).encode()

        h = hashlib.sha3_256()
        h.update(message_bytes)

        signature = self.wallet.sign(h.hexdigest())

        proof = {
            'signature': signature,
            'vk': self.wallet.verifying_key,
            'timestamp': now,
            'ip': self.ip_string
        }

        return proof


class PeerProcessor(router.Processor):
    def __init__(self, peers):
        self.peers = peers

    async def process_message(self, msg):
        return {
            'peers': [{'vk': v, 'ip': i} for v, i in self.peers.items()]
        }


class JoinProcessor(router.Processor):
    def __init__(self, ctx, peers, wallet):
        self.ctx = ctx
        self.peers = peers
        self.wallet = wallet

    async def process_message(self, msg):
        # Send ping to peer server to verify
        if not primatives.check_format(msg, rules.JOIN_MESSAGE_RULES):
            return

        vk = msg.get('vk')

        filename = str(router.DEFAULT_DIR / f'{vk}.key')
        if not os.path.exists(filename):
            return


        #
        # if not verify_proof(response, PEPPER):
        #     LOGGER.error(f'Bad proof verification for identity proof for {msg.get("ip")}')
        #     return

        if msg.get('vk') not in self.peers or self.peers[msg.get('vk')] != msg.get('ip'):
            await router.secure_multicast(msg=msg, service=JOIN_SERVICE, peer_map=self.peers, ctx=self.ctx, wallet=self.wallet)

        self.peers[msg.get('vk')] = msg.get('ip')

        return {
            'peers': [{'vk': v, 'ip': i} for v, i in self.peers.items()]
        }

# Bootnodes:
# {
#    ip: vk
# }

class Network:
    def __init__(self, wallet: Wallet, ip_string: str, ctx: zmq.asyncio.Context, router: router.Router, pepper: str=PEPPER):
        self.wallet = wallet
        self.ctx = ctx

        self.peers = {
            self.wallet.verifying_key: ip_string
        }

        # Add processors to router to accept and process networking messages
        self.ip = ip_string
        self.vk = self.wallet.verifying_key
        self.join_processor = JoinProcessor(ctx=self.ctx, peers=self.peers, wallet=self.wallet)
        self.identity_processor = IdentityProcessor(wallet=self.wallet, ip_string=ip_string, pepper=pepper)
        self.peer_processor = PeerProcessor(peers=self.peers)
        self.log = get_logger('Peers')

        router.add_service(JOIN_SERVICE, self.join_processor)
        router.add_service(IDENTITY_SERVICE, self.identity_processor)
        router.add_service(PEER_SERVICE, self.peer_processor)

        self.join_msg = {
            'ip': ip_string,
            'vk': self.wallet.verifying_key
        }

    def update_peers(self, peers):
        for peer in peers['peers']:
            self.peers[peer['vk']] = peer['ip']

    async def start(self, bootnodes: dict, vks: list):
        # Join all bootnodes
        while not self.all_vks_found(vks):

            coroutines = [router.secure_request(msg=self.join_msg, service=JOIN_SERVICE, wallet=self.wallet,
                                                ctx=self.ctx, ip=ip, vk=vk) for vk, ip, in bootnodes.items()]

            results = await asyncio.gather(*coroutines)

            for result in results:
                if result is None or result == {'response': 'ok'}:
                    continue

                # self.log.info(result)

                for peer in result['peers']:

                    response = await router.secure_request(msg={}, service=IDENTITY_SERVICE, wallet=self.wallet,
                                                           vk=peer.get('vk'),
                                                           ip=peer.get('ip'), ctx=self.ctx)

                    if response is None:
                        LOGGER.error(f'No response for identity proof for {peer.get("ip")}')
                        continue

                    if self.peers.get(peer['vk']) is None:
                        self.peers[peer['vk']] = peer['ip']
                        # self.log.info(f'{peer["vk"]} -> {peer["ip"]}')

            self.log.info(f'{len(self.peers)}/{len(vks)} peers found.')
        self.log.info(f'All peers found. Continuing startup process.')

    def all_vks_found(self, vks):
        for vk in vks:
            if self.peers.get(vk) is None:
                return False
        return True

def discover_peer(vk, ip):
    pass