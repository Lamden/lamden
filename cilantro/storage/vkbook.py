import os, math, redis
from seneca.constants.config import *
from cilantro.logger import get_logger
from cilantro.constants.vmnet import get_constitution
from cilantro.utils.utils import is_valid_hex

log = get_logger("VKBook")

class VKBook:

    r = redis.StrictRedis(host='localhost', port=get_redis_port(), db=MASTER_DB, password=get_redis_password())
    node_types = ('masternodes', 'witnesses', 'delegates')

    @classmethod
    def setup(cls, constitution_json=None):
        cls.constitution = get_constitution(constitution_json)
        for node_type in cls.node_types:
            [cls.r.hset(node_type, node['vk'], node.get('ip', 1)) for node in cls.constitution[node_type]]
        cls.bootnodes = []
        for node_type in cls.node_types:
            if env(node_type.upper()):
                cls.bootnodes += env(node_type).split(',')

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
    def get_all():
        nodes = {}
        for node_type in VKBook.node_types:
            nodes.update(VKBook.r.hgetall(node_type))
        return list(nodes.keys())

    @staticmethod
    def get_masternodes():
        return list(VKBook.r.hgetall('masternodes').keys())

    @staticmethod
    def get_delegates():
        return list(VKBook.r.hgetall('witnesses').keys())

    @staticmethod
    def get_witnesses():
        return list(VKBook.r.hgetall('delegates').keys())

    @staticmethod
    def is_node_type(node_type, vk):
        assert node_type in VKBook.node_types, 'Invalid node type!'
        return VKBook.r.hget(node_type, vk)

    @staticmethod
    def get_delegate_majority():
        return math.ceil(len(VKBook.r.hgetall('delegates')) * 2/3)

    @staticmethod
    def test_print_nodes():
        log.notice("masternodes: {}".format(VKBook.get_masternodes()))
        log.notice("witnesses: {}".format(VKBook.get_witnesses()))
        log.notice("delegates: {}".format(VKBook.get_delegates()))
