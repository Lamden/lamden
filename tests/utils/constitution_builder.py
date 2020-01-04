from cilantro_ee.crypto import Wallet

class ConstitutionBuilder:

    def __init__(self, num_masters, num_delegates, mn_min_quorum, del_min_quorum, stamps, nonces):
        self.num_masters = num_masters
        self.num_delegates = num_delegates
        self.mn_min_quorum = mn_min_quorum
        self.del_min_quorum = del_min_quorum
        self.stamps = stamps
        self.nonces = nonces
        self.build_constitution()

    def build_wallet_list(self):
        self.mn_wallets = [ Wallet() for _ in range(self.num_masters) ]
        self.dn_wallets = [ Wallet() for _ in range(self.num_delegates) ]

    def add_node(self, const, key, sub_key, sub_value):
        sub_node = {}
        sub_node[sub_key] = sub_value
        const[key] = sub_node

    def add_nodes(self, key, wallets, min_quorum):
        sk_list = [w.signing_key().hex() for w in wallets]
        self.add_node(self.sk_dict, key, 'sk_list', sk_list)
        vk_list = [w.verifying_key().hex() for w in wallets]
        self.add_node(self.const, key, 'vk_list', vk_list)
        self.const[key]['min_quorum'] = min_quorum

    def build_constitution(self):
        self.sk_dict = {}
        self.const = {}
        self.build_wallet_list()
        self.add_nodes('masternodes', self.mn_wallets, self.mn_min_quorum)
        self.add_nodes('delegates', self.dn_wallets, self.del_min_quorum)
        self.const['enable_stamps'] = self.stamps
        self.const['enable_nonces'] = self.nonces

    def get_constitution(self) -> dict:
        return self.const

    def get_mn_wallets(self) -> list:
        return self.mn_wallets

    def get_del_wallets(self) -> list:
        return self.dn_wallets

    def get_vk_list(self, key) -> list:
        return self.const[key]['vk_list']

    def get_sk_list(self, key) -> list:
        return self.sk_dict[key]['sk_list']

    def get_vk(self, key, idx):
        return self.const[key]['vk_list']

    def get_sk(self, key, idx):
        return self.sk_dict[key]['sk_list'][idx]
