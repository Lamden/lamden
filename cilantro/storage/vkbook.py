import os, math
from seneca.constants.config import *
from cilantro.logger import get_logger
from cilantro.constants.vmnet import get_constitution
from cilantro.utils.utils import is_valid_hex
from collections import defaultdict

log = get_logger("VKBook")

class VKBook:

    node_types = ('masternode', 'witness', 'delegate')
    node_types_map = {
        'masternode': 'masternodes',
        'witness': 'witnesses',
        'delegate': 'delegates'
    }
    bootnodes = []
    constitution = defaultdict(list)
    book = defaultdict(dict)

    @classmethod
    def setup(cls, constitution_json=None):
        cls.bootnodes = []
        if os.getenv('__TEST__') or os.getenv('TEST_NAME'):
            from cilantro.constants.testnet import TESTNET_DELEGATES, TESTNET_WITNESSES, TESTNET_MASTERNODES
            for node in TESTNET_MASTERNODES:
                cls.book['masternode'][node['vk']] = True
                cls.constitution['masternodes'].append(node)
            for node in TESTNET_WITNESSES:
                cls.book['witness'][node['vk']] = True
                cls.constitution['witnesses'].append(node)
            for node in TESTNET_DELEGATES:
                cls.book['delegate'][node['vk']] = True
                cls.constitution['delegates'].append(node)
        else:
            cls.constitution = get_constitution(constitution_json)
            for node_type in cls.node_types:
                nt = cls.node_types_map.get(node_type, node_type)
                for node in cls.constitution[nt]:
                    cls.book[nt][node['vk']] = node.get('ip', True)
            for node_type in cls.node_types:
                node_list = env(node_type.upper())
                if node_list:
                    cls.bootnodes += node_list.split(',')

    @staticmethod
    def add_node(vk, node_type, ip=None):
        assert node_type in VKBook.node_types, 'Invalid node type!'
        assert is_valid_hex(vk, length=64), 'Invalid VK!'
        creds = {'vk': vk}
        if ip:
            encoded_ip = ip.encode()
            creds.update({'ip': ip})
        else:
            encoded_ip = 1
        cls.book[node_type][vk] = encoded_ip

    @classmethod
    def get_all(cls):
        nodes = {}
        for node_type in VKBook.node_types:
            nodes.update(cls.book[node_type])
        return list(nodes.keys())

    @classmethod
    def get_masternodes(cls):
        return list(cls.book['masternode'].keys())

    @classmethod
    def get_witnesses(cls):
        return list(cls.book['witness'].keys())

    @classmethod
    def get_delegates(cls):
        return list(cls.book['delegate'].keys())

    @classmethod
    def is_node_type(cls, node_type, vk):
        assert node_type in cls.node_types, 'Invalid node type!'
        return cls.book[node_type].get(vk) != None

    @classmethod
    def get_delegate_majority(cls):
        return math.ceil(len(cls.book['delegate']) * 2/3)

    @staticmethod
    def test_print_nodes():
        log.notice("masternodes: {}".format(VKBook.get_masternodes()))
        log.notice("witnesses: {}".format(VKBook.get_witnesses()))
        log.notice("delegates: {}".format(VKBook.get_delegates()))

if os.getenv('__TEST__'):
    VKBook.setup()
