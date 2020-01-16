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

        self.masternode_quorum_min = min(self.masternode_quorum_max,
                                      self.contract.get_masternode_quorum_min())
        self.delegate_quorum_min = min(self.delegate_quorum_max,
                                      self.contract.get_delegate_quorum_min())

    @property
    def masternodes(self):
        return self.contract.quick_read('masternode_list')

    @property
    def delegates(self):
        return self.contract.quick_read('delegate_list')

    @property
    def core_nodes(self):
        return self.masternodes + self.delegates