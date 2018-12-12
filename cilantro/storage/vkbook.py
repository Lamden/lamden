import os, math, redis
from seneca.constants.config import *
from cilantro.logger import get_logger
from cilantro.constants.vmnet import get_constitution
from cilantro.utils.utils import is_valid_hex

log = get_logger("VKBook")

class VKBook:

    r = redis.StrictRedis(host='localhost', port=get_redis_port(), db=MASTER_DB, password=get_redis_password())
    node_types = ('masternode', 'witness', 'delegate')
    node_types_map = {
        'masternode': 'masternodes',
        'witness': 'witnesses',
        'delegate': 'delegates'
    }
    bootnodes = []

    @classmethod
    def setup(cls, constitution_json=None):
        cls.bootnodes = []
        if os.getenv('__TEST__') or os.getenv('TEST_NAME'):
            from cilantro.constants.testnet import TESTNET_DELEGATES, TESTNET_WITNESSES, TESTNET_MASTERNODES
            cls.constitution = {
                'masternode': [cls.r.hset('masternode', node['vk'], node.get('ip', 1)) for node in TESTNET_MASTERNODES],
                'witness': [cls.r.hset('witness', node['vk'], node.get('ip', 1)) for node in TESTNET_WITNESSES],
                'delegate': [cls.r.hset('delegate', node['vk'], node.get('ip', 1)) for node in TESTNET_DELEGATES]
            }
        else:
            cls.constitution = get_constitution(constitution_json)
            for node_type in cls.node_types:
                [cls.r.hset(node_type, node['vk'], node.get('ip', 1)) for node in cls.constitution[cls.node_types_map.get(node_type, node_type)]]
            for node_type in cls.node_types:
                node_list = env(node_type.upper())
                if node_list:
                    cls.bootnodes += node_list.split(',')

    @staticmethod
    def blind_trust_vk(vk, node_type, ip=None):
        assert node_type in VKBook.node_types, 'Invalid node type!'
        assert is_valid_hex(vk, length=64), 'Invalid VK!'
        creds = {'vk': vk}
        if ip:
            encoded_ip = ip.encode()
            creds.update({'ip': ip})
        else:
            encoded_ip = 1
        VKBook.hset(node_type, vk, encoded_ip)
        cls.constitution[node_type].append(creds)

    @staticmethod
    def decode(l):
        return [i.decode() for i in l]

    @staticmethod
    def get_all():
        nodes = {}
        for node_type in VKBook.node_types:
            nodes.update(VKBook.r.hgetall(node_type))
        return VKBook.decode(nodes.keys())

    @staticmethod
    def get_masternodes():
        return VKBook.decode(VKBook.r.hgetall('masternode').keys())

    @staticmethod
    def get_witnesses():
        return VKBook.decode(VKBook.r.hgetall('witness').keys())

    @staticmethod
    def get_delegates():
        return VKBook.decode(VKBook.r.hgetall('delegate').keys())

    @staticmethod
    def is_node_type(node_type, vk):
        assert node_type in VKBook.node_types, 'Invalid node type!'
        return VKBook.r.hget(node_type, vk)

    @staticmethod
    def get_delegate_majority():
        return math.ceil(len(VKBook.r.hgetall('delegate')) * 2/3)

    @staticmethod
    def test_print_nodes():
        log.notice("masternodes: {}".format(VKBook.get_masternodes()))
        log.notice("witnesses: {}".format(VKBook.get_witnesses()))
        log.notice("delegates: {}".format(VKBook.get_delegates()))

if os.getenv('__TEST__'):
    VKBook.setup()
