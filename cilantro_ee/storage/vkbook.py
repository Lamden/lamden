import math
from cilantro_ee.logger import get_logger
from cilantro_ee.utils.utils import is_valid_hex
from collections import defaultdict
from cilantro_ee.constants import conf
from cilantro_ee.contracts import sync
from cilantro_ee.utils.test.testnet_config import read_public_constitution
from contracting.client import ContractingClient

log = get_logger("VKBook")

INITIALIZED = False
DEBUG = True

class ReplacementVKBook:
    def __init__(self):
        self.client = ContractingClient()

        self.contract = self.client.get_contract('vkbook')
        if self.contract is None or DEBUG:
            book = read_public_constitution(conf.CONSTITUTION_FILE)
            mns = [node['vk'] for node in book['masternodes']]
            dels = [node['vk'] for node in book['delegates']]

            # Put VKs into VKBook smart contract and submit it to state
            sync.submit_contract_with_construction_args('vkbook', args={'masternodes': mns,
                                                                        'delegates': dels,
                                                                        'stamps': conf.STAMPS_ENABLED,
                                                                        'nonces': conf.NONCE_ENABLED})

            self.contract = self.client.get_contract('vkbook')

        self.boot_quorum_masternodes = len(self.masternodes)
        self.boot_quorum_delegates = len(self.delegates)

        self.boot_quorum = self.boot_quorum_masternodes + self.boot_quorum_delegates

    @property
    def stamps_enabled(self):
        return self.contract.get_stamps_enabled()

    @property
    def nonces_enabled(self):
        return self.contract.get_nonces_enabled()

    @property
    def masternodes(self):
        return self.contract.get_masternodes()

    @property
    def delegates(self):
        return self.contract.get_delegates()

    @property
    def witnesses(self):
        return self.contract.get_witnesses()

    @property
    def notifiers(self):
        return self.contract.get_notifiers()

    @property
    def schedulers(self):
        return self.contract.get_schedulers()

    @property
    def state_sync(self):
        return self.masternodes + self.delegates

    @property
    def all(self):
        return self.masternodes + self.delegates + self.witnesses


PhoneBook = ReplacementVKBook()


class VKBook:
    node_types = ('masternode', 'witness', 'delegate')
    node_types_map = {
        'masternode': 'masternodes',
        'witness': 'witnesses',
        'delegate': 'delegates'
    }
    book = defaultdict(list)
    # witness_mn_map = {}
    # delegate_mn_map = {}

    SETUP = False

    BOOT_QUORUM = 0
    BOOT_QUORUM_MASTERNODES = 0
    BOOT_QUORUM_DELEGATES = 0

    @classmethod
    def setup(cls):
        if not cls.SETUP:
            # TODO untangle this mess --davis
            from cilantro_ee.utils.test.testnet_config import read_public_constitution

            const_file = conf.CONSTITUTION_FILE
            if const_file:
                log.info("VKBook using constitution file {}".format(const_file))
                book = read_public_constitution(const_file)
                mns = book['masternodes']
                dels = book['delegates']
                wits = book['witnesses']
                scheds = book['schedulers'] if 'schedulers' in book else []
                notifs = book['notifiers'] if 'notifiers' in book else []
            else:
                log.info("No constitution file detected. Using TESTNET VKs")
                from cilantro_ee.constants.testnet import TESTNET_DELEGATES, TESTNET_MASTERNODES, TESTNET_WITNESSES, set_testnet_nodes
                set_testnet_nodes()
                mns = TESTNET_MASTERNODES
                dels = TESTNET_DELEGATES
                wits = TESTNET_WITNESSES
                scheds, notifs = [], []

            for node in mns:
                cls.book['masternodes'].append(node['vk'])
            for node in wits:
                cls.book['witnesses'].append(node['vk'])
            for node in dels:
                cls.book['delegates'].append(node['vk'])
            for node in scheds:
                cls.book['schedulers'].append(node['vk'])
            for node in notifs:
                cls.book['notifiers'].append(node['vk'])

            # cls._build_mn_witness_maps()
            cls.SETUP = True

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
    def get_witnesses(cls) -> list:
        return cls.book['witnesses']

    @classmethod
    def get_delegates(cls) -> list:
        return cls.book['delegates']

    @classmethod
    def get_schedulers(cls) -> list:
        return cls.book['schedulers']

    @classmethod
    def get_notifiers(cls) -> list:
        return cls.book['notifiers']

    @classmethod
    def get_state_syncs(cls) -> list:
        return cls.get_schedulers() + cls.get_notifiers() + cls.get_delegates() + cls.get_masternodes()

    @classmethod
    def is_node_type(cls, node_type, vk):
        assert node_type in cls.node_types, 'Invalid node type!'
        return vk in cls.book[cls.node_types_map[node_type]]

    @classmethod
    def get_delegate_majority(cls):
        return math.ceil(len(cls.get_delegates()) * 2/3)

    @staticmethod
    def test_print_nodes():
        log.notice("masternodes: {}".format(VKBook.get_masternodes()))
        log.notice("witnesses: {}".format(VKBook.get_witnesses()))
        log.notice("delegates: {}".format(VKBook.get_delegates()))

    @classmethod
    def get_mns_for_delegate_vk(cls, vk) -> list:
        """ Returns a list of Masternode VKs that a given delegate vk is responsible to subscribing to (on the
        TransactionBatcher socket) """
        assert vk in cls.delegate_mn_map, "Delegate VK {} not found in delegate_mn_map {}".format(vk, cls.delegate_mn_map)
        return cls.delegate_mn_map[vk]

    # @classmethod
    # def _build_mn_witness_maps(cls):
    #     r = 1
    #     for i, mn_vk in enumerate(VKBook.get_masternodes()):
    #         witnesses = VKBook.get_witnesses()[i * r:i * r + r]
    #         delegates = VKBook.get_delegates()[i * r:i * r + r]
    #
    #         for w in delegates:
    #             cls.delegate_mn_map[w] = mn_vk
    #
    #         for w in witnesses:
    #             cls.witness_mn_map[w] = mn_vk
    #
    #     # TODO remove
    #     log.notice("DELEGATE_MN_MAP: {}".format(cls.delegate_mn_map))
    #     log.notice("WITNESS_MN_MAP: {}".format(cls.witness_mn_map))

VKBook.setup()
