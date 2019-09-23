from cilantro_ee.storage.state import MetaDataStorage
from contracting.client import ContractingClient

import capnp
import os
from cilantro_ee.messages import capnp as schemas

blockdata_capnp = capnp.load(os.path.dirname(schemas.__file__) + '/blockdata.capnp')

PENDING_REWARDS_KEY = b'__rewards'


class RewardManager:
    def __init__(self, driver=MetaDataStorage(), client=ContractingClient()):
        self.driver = driver
        self.client = client

    def issue_rewards(self):
        master_ratio, delegate_ratio, burn_ratio, foundation_ratio = self.reward_ratio


    @property
    def pending_rewards(self):
        return self.driver.get(PENDING_REWARDS_KEY)

    @property
    def stamps_per_tau(self):
        pass

    def stamps_in_block(self, block):
        pass

    def add_pending_rewards(self, block):
        pass

    @property
    def reward_ratio(self):
        return [0, 0, 0, 0]

    def get_masternodes(self):
        pass

    def get_delegates(self):
        pass

    def get_foundation(self):
        pass