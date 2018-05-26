import json
import os
from decimal import getcontext
import sys
import hashlib

def snake_to_pascal(s):
    s = s.split('-')
    new_str = ''
    for ss in s:
        new_str += ss.title()
    return new_str

def gen_keypair(url):
    """
    Computes a wallet key pair as a deterministic function of url
    """
    # from cilantro.protocol.wallets import ED25519Wallet
    import cilantro.protocol.wallets.ed25519
    h = hashlib.sha256()
    h.update(url.encode())
    return cilantro.protocol.wallets.ed25519.ED25519Wallet.new(seed=h.digest())

def config_testnet(testnet: dict) -> dict:
    """
    Dynamically builds nodes url and wallet info for testing purposes
    - Constants.Testnet.Witnesses and Constants.Testnet.Delegates will return lists of dictionaries,
      where each dict has keys 'url', 'sk', and 'vk'
    - Constants.Testnet.AllNodes will return a dict of all node with just keys as urls and values as verifying keys
    - Since there is only one Masternode (at least rn), Constants.Testnet.Masternode must be referenced using
      Constants.Testnet.Masternode.InternalUrl, Constants.Testnet.Masternode.ExternalUrl, --.Vk and --.Sk
    """
    SLOTS_PER_NODE = 4  # distance between port assignments for each node
    all_nodes = {}

    if os.getenv('MASTERNODE'):
        masternode = os.getenv('MASTERNODE')
        delegates = os.getenv('DELEGATE').split(',')
        witnesses = os.getenv('WITNESS').split(',')

        mn_url = 'tcp://{}:5555'.format(masternode)
        mn_sk, mn_vk = gen_keypair(mn_url)
        all_nodes[mn_url] = mn_vk
        testnet['masternode']['internal-url'] = mn_url
        testnet['masternode']['host'] = masternode
        testnet['masternode']['vk'] = mn_vk
        testnet['masternode']['sk'] = mn_sk

        node_ips = {'delegates': delegates, 'witnesses': witnesses}

        for key, node_list in node_ips.items():
            nodes = []
            for i, ip in enumerate(node_list):
                url = 'tcp://{}:6000'.format(ip)
                sk, vk = gen_keypair(url)
                nodes.append({'url': url, 'sk': sk, 'vk': vk})
                all_nodes[url] = vk
            testnet[key] = nodes
    else:
        mn_url = testnet['masternode']['internal-url']
        mn_sk, mn_vk = gen_keypair(mn_url)
        testnet['masternode']['vk'] = mn_vk
        testnet['masternode']['sk'] = mn_sk
        all_nodes[mn_url] = mn_vk

        for node_type in ('delegates', 'witnesses'):
            nodes = []
            base_url, num, port_start = testnet[node_type]['host'], testnet[node_type]['num'], \
                                        int(testnet[node_type]['port_start'])
            for i in range(num):
                url = "{}:{}".format(base_url, port_start + i * SLOTS_PER_NODE)
                sk, vk = gen_keypair(url)
                nodes.append({'url': url, 'sk': sk, 'vk': vk})
                all_nodes[url] = vk

            testnet[node_type] = nodes

    testnet['all-nodes'] = all_nodes
    return testnet

    # Add masternode wallet and url to all_nodes
    # mn_url = testnet['masternode']['internal-url']



path = os.path.join(os.path.dirname(__file__), 'config.json')
config = json.load(open(path))

# Add /messages/capnp to Python path. We need these loaded for capnp magic imports
sys.path.append(os.path.dirname(__file__) + '/messages/capnp')


class Constants:
    classes = []
    json = None

    @classmethod
    def new_class(cls, name, **kwargs):
        c = type(name, (cls,), kwargs)
        globals()[name] = c
        return c

    @classmethod
    def add_attr(cls, name, value):
        setattr(cls, name, value)

    @classmethod
    def build_from_json(cls, d, last_class=None):
        for k in d.keys():
            if type(d[k]) == dict:
                new_class = cls.new_class(name=snake_to_pascal(k))
                cls.add_attr(name=snake_to_pascal(k), value=new_class)
                cls.classes.append(new_class)
                cls.build_from_json(d[k], last_class=new_class)
            else:
                setattr(last_class, snake_to_pascal(k), d[k])

    @classmethod
    def __str__(cls):
        return str(cls.json)

# Constants.load_to_env(config)
Constants.build_from_json(config)
# print(os.environ)
Constants.json = config

c = __import__('cilantro.protocol.proofs', fromlist=[Constants.Protocol.Proofs])
Constants.Protocol.Proofs = getattr(c, Constants.Protocol.Proofs)

c = __import__('cilantro.protocol.wallets', fromlist=[Constants.Protocol.Wallets])
Constants.Protocol.Wallets = getattr(c, Constants.Protocol.Wallets)

c = __import__('cilantro.protocol.interpreters', fromlist=[Constants.Protocol.Interpreters])
Constants.Protocol.Interpreters = getattr(c, Constants.Protocol.Interpreters)

# Config fixed point decimals
getcontext().prec = Constants.Protocol.SignificantDigits

# Load all messages classes. We need Python to interpret all of the class definitions, so the metaprogramming hooks
# are executed properly and the MessageBase registry is created (the MessageBase.registry)
# from cilantro.messages import *
