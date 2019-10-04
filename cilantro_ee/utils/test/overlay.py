"""
Utility functions for tests.
"""
import random
import hashlib
from struct import pack

from zmq.utils.z85 import decode, encode
from nacl.public import PrivateKey
from nacl.signing import SigningKey, VerifyKey
from nacl.bindings import crypto_sign_ed25519_sk_to_curve25519

from cilantro_ee.services.overlay.kademlia.node import Node

def mknode(node_id=None, ip=None, port=None, intid=None):
    """
    Make a node.  Created a random id if not specified.
    """
    if intid is not None:
        node_id = pack('>l', intid)
    if not node_id:
        randbits = str(random.getrandbits(255))
        node_id = hashlib.sha1(randbits.encode()).digest()
    return Node(node_id, ip, port)

def genkeys(sk_hex):
    sk = SigningKey(seed=bytes.fromhex(sk_hex))
    vk = sk.verify_key.encode().hex()
    public_key = VerifyKey(bytes.fromhex(vk)).to_curve25519_public_key()._public_key
    private_key = crypto_sign_ed25519_sk_to_curve25519(sk._signing_key)
    return {
        'sk': sk_hex,
        'vk': vk,
        'public_key': public_key.hex(),
        'secret_key': private_key.hex(),
        'private_key': encode(private_key),
        'curve_key': encode(public_key)
    }

class FakeProtocol:
    def __init__(self, sourceID, ksize=20):
        self.router = RoutingTable(self, ksize, Node(sourceID))
        self.storage = {}
        self.sourceID = sourceID
