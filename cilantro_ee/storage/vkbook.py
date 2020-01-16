from contracting.client import ContractingClient
import math


class VKBook:
    def __init__(self, boot_mn, boot_del, client=ContractingClient()):
        self.boot_mn = boot_mn
        self.boot_del = boot_del
        self.reload(client)

    def reload(self, client=ContractingClient()):
        self.masternodes_contract = client.get_contract('masternodes')

        assert self.masternodes_contract is not None, 'Masternodes not in state.'

        self.delegates_contract = client.get_contract('delegates')

        assert self.masternodes_contract is not None, 'Delegates not in state.'

    @property
    def masternode_quorum_max(self):
        return int(len(self.masternodes) * 2 / 3) + 1

    @property
    def masternode_quorum_min(self):
        return min(self.masternode_quorum_max, self.boot_mn)

    @property
    def delegate_quorum_max(self):
        return int(len(self.delegates) * 2 / 3) + 1

    @property
    def delegate_quorum_min(self):
        return min(self.delegate_quorum_max, self.boot_del)

    @property
    def masternodes(self):
        return self.masternodes_contract.quick_read('S', 'members')

    @property
    def delegates(self):
        return self.delegates_contract.quick_read('S', 'members')

    @property
    def core_nodes(self):
        return self.masternodes + self.delegates
