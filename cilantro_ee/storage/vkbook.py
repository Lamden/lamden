from cilantro_ee.logger import get_logger
from cilantro_ee.constants import conf
from cilantro_ee.contracts import sync
from cilantro_ee.utils.test.testnet_config import read_public_constitution
from contracting.client import ContractingClient

log = get_logger("VKBook")


class VKBook:
    def __init__(self, masternodes, delegates, stamps, nonces, debug=True):
        self.client = ContractingClient()

        self.contract = self.client.get_contract('vkbook')

        if self.contract is None or debug:
            # Put VKs into VKBook smart contract and submit it to state
            sync.submit_contract_with_construction_args('vkbook', args={'masternodes': masternodes,
                                                                        'delegates': delegates,
                                                                        'stamps': stamps,
                                                                        'nonces': nonces})

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


book = read_public_constitution(conf.CONSTITUTION_FILE)
masternodes = [node['vk'] for node in book['masternodes']]
delegates = [node['vk'] for node in book['delegates']]
PhoneBook = VKBook(masternodes, delegates, stamps=conf.STAMPS_ENABLED, nonces=conf.NONCE_ENABLED)
