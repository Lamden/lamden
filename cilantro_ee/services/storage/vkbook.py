from contracting.client import ContractingClient
import math


class VKBook:
    def __init__(self, client=ContractingClient()):
        self.client = client
        self.contract = self.client.get_contract('vkbook')

        assert self.contract is not None, 'VKBook not in state.'

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
