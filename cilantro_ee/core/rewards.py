from cilantro_ee.storage.state import MetaDataStorage
from contracting.client import ContractingClient

class RewardManager:
    def __init__(self, driver=MetaDataStorage()):
        self.driver = driver

    def issue_rewards(self):
        master_ratio, delegate_ratio, burn_ratio, foundation_ratio = self.reward_ratio



    @property
    def pending_rewards(self):
        pass

    @property
    def stamps_per_tau(self):
        pass

    def add_pending_rewards(self, block):
        pass

    @property
    def reward_ratio(self):
        return [0, 0, 0, 0]
