import os, math
from seneca.constants.config import *
from cilantro.logger import get_logger
from cilantro.utils.utils import is_valid_hex
from collections import defaultdict
from cilantro.utils.test.testnet_config import get_testnet_config

log = get_logger("VKBook")


class VKBookMeta(type):
    def __new__(cls, clsname, bases, clsdict):
        clsobj = super().__new__(cls, clsname, bases, clsdict)

        assert hasattr(clsobj, 'setup'), "Class obj {} expected to have method called 'setup'".format(clsobj)
        clsobj.setup()

        return clsobj


class VKBook(metaclass=VKBookMeta):

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
    def setup(cls):
        cls.bootnodes = []

        if os.getenv('WHAT_IS_THIS_FLAG_CALLED_LOL', None):
            pass
            # TODO -- check for an env var here, and if we are deploying on docker/cloud use the config file specified
            # in this node's bootstrap config file
        else:
            cls.constitution = get_testnet_config()

        for node_type in cls.node_types_map:
            for node in cls.constitution[cls.node_types_map.get(node_type)]:
                cls.book[node_type][node['vk']] = node.get('ip', True)

        for node_type in cls.node_types:
            node_list = env(node_type.upper())
            if node_list:
                cls.bootnodes += node_list.split(',')

    @classmethod
    def add_node(cls, vk, node_type, ip=None):
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
        return cls.book[node_type].get(vk) is not None

    @classmethod
    def get_delegate_majority(cls):
        return math.ceil(len(cls.book['delegate']) * 2/3)

    @staticmethod
    def test_print_nodes():
        log.notice("masternodes: {}".format(VKBook.get_masternodes()))
        log.notice("witnesses: {}".format(VKBook.get_witnesses()))
        log.notice("delegates: {}".format(VKBook.get_delegates()))
