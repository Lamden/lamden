from contracting.client import ContractingClient
import math


class VKBook:
    def __init__(self, client=ContractingClient()):
        self.reload(client)

    def reload(self, client=ContractingClient()):
        self.contract = client.get_contract('vkbook')

        assert self.contract is not None, 'VKBook not in state.'

        self.masternode_quorum_max = math.ceil(len(self.masternodes) * 2 / 3)
        self.delegate_quorum_max = math.ceil(len(self.delegates) * 2 / 3)
        self.witness_quorum_max = math.ceil(len(self.witnesses) * 2 / 3)
        self.notifier_quorum_max = math.ceil(len(self.notifiers) * 2 / 3)
        self.scheduler_quorum_max = math.ceil(len(self.schedulers) * 2 / 3)

        self.masternode_quorum_min = min(self.masternode_quorum_max,
                                      self.contract.get_masternode_quorum_min())
        self.delegate_quorum_min = min(self.delegate_quorum_max,
                                      self.contract.get_delegate_quorum_min())
        self.witness_quorum_min = min(self.witness_quorum_max,
                                      self.contract.get_witness_quorum_min())
        self.notifier_quorum_min = min(self.notifier_quorum_max,
                                      self.contract.get_notifier_quorum_min())
        self.scheduler_quorum_min = min(self.scheduler_quorum_max,
                                      self.contract.get_scheduler_quorum_min())


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
    def core_nodes(self):
        return self.masternodes + self.delegates
