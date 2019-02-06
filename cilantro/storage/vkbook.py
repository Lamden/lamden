import os, math
from cilantro.logger import get_logger
from cilantro.utils.utils import is_valid_hex
from collections import defaultdict

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
    book = defaultdict(list)

    @classmethod
    def setup(cls):
        # TODO untangle this mess --davis
        from cilantro.constants.testnet import TESTNET_DELEGATES, TESTNET_MASTERNODES, TESTNET_WITNESSES
        from cilantro.utils.test.testnet_config import read_public_constitution

        const_file = os.getenv('CONSTITUTION_FILE', None)
        if const_file:
            log.info("VKBook using constitution file {}".format(const_file))
            book = read_public_constitution(const_file)
            mns = book['masternodes']
            dels = book['delegates']
            wits = book['witnesses']
        else:
            log.info("No constitution file detected. Using TESTNET VKs")
            mns = TESTNET_MASTERNODES
            dels = TESTNET_DELEGATES
            wits = TESTNET_WITNESSES

        for node in mns:
            cls.book['masternodes'].append(node['vk'])
        for node in dels:
            cls.book['witnesses'].append(node['vk'])
        for node in wits:
            cls.book['delegates'].append(node['vk'])

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
        return cls.get_masternodes() + cls.get_delegates() + cls.get_witnesses()

    @classmethod
    def get_masternodes(cls):
        return cls.book['masternodes']

    @classmethod
    def get_witnesses(cls):
        return cls.book['witnesses']

    @classmethod
    def get_delegates(cls):
        return cls.book['delegates']

    @classmethod
    def is_node_type(cls, node_type, vk):
        assert node_type in cls.node_types, 'Invalid node type!'
        # if node_type == 'masternode':
        #     log.important("vk {} checking if masternode in book {}".format(vk, cls.book))
        #     log.important("correspoinding nodes for type: {}".format(cls.book[cls.node_types_map[node_type]]))
        return vk in cls.book[cls.node_types_map[node_type]]

    @classmethod
    def get_delegate_majority(cls):
        return math.ceil(len(cls.get_delegates()) * 2/3)

    @staticmethod
    def test_print_nodes():
        log.notice("masternodes: {}".format(VKBook.get_masternodes()))
        log.notice("witnesses: {}".format(VKBook.get_witnesses()))
        log.notice("delegates: {}".format(VKBook.get_delegates()))
