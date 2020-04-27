from contracting.client import ContractingClient
from contracting.db.driver import ContractDriver
import capnp
import os
from cilantro_ee.messages.capnp_impl import capnp_struct as schemas
from cilantro_ee.logger.base import get_logger

from decimal import Decimal
import decimal
from contracting.stdlib.bridge.decimal import ContractingDecimal

blockdata_capnp = capnp.load(os.path.dirname(schemas.__file__) + '/blockdata.capnp')

PENDING_REWARDS_KEY = '__rewards'


class RewardManager:
    def __init__(self, driver=ContractDriver(), debug=True):
        self.driver = driver
        self.client = ContractingClient(driver=driver)

        # All of this can be just derived from the blockchain driver without marking reads
        # Should marks on default be false?
        self.stamp_contract = self.client.get_contract('stamp_cost')
        self.reward_contract = self.client.get_contract('rewards')
        self.currency_contract = self.client.get_contract('currency')
        self.election_house = self.client.get_contract('election_house')
        self.foundation_contract = self.client.get_contract('foundation')
        self.masternodes_contract = self.client.get_contract('masternodes')
        self.delegates_contract = self.client.get_contract('delegates')

        assert self.stamp_contract is not None, 'Stamp contract not in state.'
        assert self.reward_contract is not None, 'Reward contract not in state.'
        assert self.currency_contract is not None, 'Currency contract not in state.'
        assert self.foundation_contract is not None, 'Foundation contract not in state.'
        assert self.masternodes_contract is not None, 'Masternodes not in state.'
        assert self.delegates_contract is not None, 'Delegates not in state.'

        self.log = get_logger('RWM')
        self.log.propagate = debug

        self.dust_exponent = 8

    def issue_rewards(self, block):
        master_ratio, delegate_ratio, burn_ratio, foundation_ratio = self.reward_ratio

        stamps = self.stamps_in_block(block)

        self.log.info(f'{stamps} stamps in this block to issue.')

        pending_rewards = self.stamps_in_block(block) / self.stamps_per_tau

        self.log.info(f'{pending_rewards} tau in this block to issue.')

        masters = self.masternodes_contract.quick_read('S', 'members')
        delegates = self.delegates_contract.quick_read('S', 'members')

        total_shares = len(masters) + len(delegates) + 1

        reward_share = Decimal(str(pending_rewards / total_shares))

        master_reward = reward_share * Decimal(str(master_ratio))
        delegate_reward = reward_share * Decimal(str(delegate_ratio))
        foundation_reward = reward_share * Decimal(str(foundation_ratio))
        # BURN + DEVELOPER

        decimal.getcontext().rounding = decimal.ROUND_DOWN

        master_reward = round(master_reward, self.dust_exponent)
        delegate_reward = round(delegate_reward, self.dust_exponent)
        foundation_reward = round(foundation_reward, self.dust_exponent)

        for m in masters:
            self.add_to_balance(vk=m, amount=master_reward)

        for d in delegates:
            self.add_to_balance(vk=d, amount=delegate_reward)

        self.add_to_balance(vk=self.foundation_contract.owner.get(), amount=foundation_reward)

    def add_to_balance(self, vk, amount):
        current_balance = self.driver.get_var(contract='currency', variable='balances', arguments=[vk], mark=False)

        if current_balance is None:
            current_balance = ContractingDecimal(0)

        amount = ContractingDecimal(amount)
        self.log.info('Sending {} to {}. New bal: {} -> {}'.format(amount, vk[:8], current_balance, amount + current_balance))

        self.driver.set_var(
            contract='currency',
            variable='balances',
            arguments=[vk],
            value=amount + current_balance,
            mark=False
        )

    # def get_pending_rewards(self):
    #     key = self.driver.get(PENDING_REWARDS_KEY)
    #
    #     if key is None:
    #         key = 0
    #
    #     return key

    # def set_pending_rewards(self, value):
    #     self.driver.set(PENDING_REWARDS_KEY, value=value, mark=False)

    @property
    def stamps_per_tau(self):
        return self.stamp_contract.quick_read('S', 'value')

    @staticmethod
    def stamps_in_block(block):
        total = 0

        for sb in block['subBlocks']:
            for tx in sb['transactions']:
                total += tx['stampsUsed']

        return total

    @staticmethod
    def stamps_in_subblock(subblock):
        if type(subblock) != dict:
            subblock = subblock.to_dict()

        total = 0

        for tx in subblock['transactions']:
            total += tx['stampsUsed']

        return total

    # def add_pending_rewards(self, subblock):
    #     current_rewards = self.get_pending_rewards()
    #     used_stamps = self.stamps_in_subblock(subblock)
    #
    #     rewards_as_tau = used_stamps / self.stamps_per_tau
    #     self.set_pending_rewards(current_rewards + rewards_as_tau)

    @property
    def reward_ratio(self):
        return self.reward_contract.quick_read(variable='S', args=['value'])
