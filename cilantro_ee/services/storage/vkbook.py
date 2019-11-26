from cilantro_ee.core.logger import get_logger
from cilantro_ee.constants import conf
from cilantro_ee.contracts import sync
from contracting.client import ContractingClient
import cilantro_ee
import math
import json, os
from os.path import join

log = get_logger("VKBook")

# need to refactor this code of vkbook
PUBLIC_JSON_DIR = os.path.dirname(cilantro_ee.__path__[-1]) + '/constitutions/public'

def read_public_constitution(filename) -> dict:
    fpath = PUBLIC_JSON_DIR + '/' + filename
    assert os.path.exists(fpath), "No public constitution file found at path {}".format(fpath)
    with open(fpath) as f:
        return json.load(f)


class VKBook:
    def __init__(self, masternodes, delegates, num_boot_mns=1,
                 num_boot_del=1, stamps=True, nonces=False, debug=True):
        self.client = ContractingClient()

        self.contract = self.client.get_contract('vkbook')

        if self.contract is None or debug:
            # Put VKs into VKBook smart contract and submit it to state
            sync.submit_contract_with_construction_args('vkbook', args={'masternodes': masternodes,
                                                                        'delegates': delegates,
                                                                        'num_boot_mns': num_boot_mns,
                                                                        'num_boot_del': num_boot_del,
                                                                        'stamps': stamps,
                                                                        'nonces': nonces})

            self.contract = self.client.get_contract('vkbook')

        self.masternode_quorum_max = math.ceil(len(self.masternodes) * 2 / 3)

        self.delegate_quorum_max = math.ceil(len(self.delegates) * 2 / 3)

        num_boot_mns = self.contract.get_num_boot_masternodes()

        self.masternode_quorum_min = min(self.masternode_quorum_max, num_boot_mns)

        num_boot_del = self.contract.get_num_boot_delegates()

        self.delegate_quorum_min = min(self.delegate_quorum_max, num_boot_del)

        self.quorum_min = self.masternode_quorum_min + self.delegate_quorum_min


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

    @property
    def num_boot_masternodes(self):
        return self.contract.get_num_boot_masternodes()

    @property
    def num_boot_delegates(self):
        return self.contract.get_num_boot_delegates()


book = read_public_constitution(conf.CONSTITUTION_FILE)
masternodes = [node['vk'] for node in book['masternodes']]
delegates = [node['vk'] for node in book['delegates']]

# print('masternodes before Phonebook init: {}'.format(masternodes))
# print('delegates before Phonebook init: {}'.format(delegates))

PhoneBook = VKBook(masternodes=masternodes,
                   delegates=delegates,
                   num_boot_mns=len(conf.BOOT_MASTERNODE_IP_LIST),
                   num_boot_del=len(conf.BOOT_DELEGATE_IP_LIST),
                   stamps=conf.STAMPS_ENABLED,
                   nonces=conf.NONCE_ENABLED)

