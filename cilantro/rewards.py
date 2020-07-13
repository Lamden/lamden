import decimal

from contracting.stdlib.bridge.decimal import ContractingDecimal
from contracting.client import ContractingClient

from cilantro.logger.base import get_logger

decimal.getcontext().rounding = decimal.ROUND_DOWN

REQUIRED_CONTRACTS = [
    'stamp_cost',
    'rewards',
    'currency',
    'election_house',
    'foundation',
    'masternodes',
    'delegates'
]
DUST_EXPONENT = 8

log = get_logger('Rewards')


class RewardManager:
    @staticmethod
    def contract_exists(name: str, client: ContractingClient):
        return client.get_contract(name) is not None

    @staticmethod
    def is_setup(client: ContractingClient):
        for contract in REQUIRED_CONTRACTS:
            if not RewardManager.contract_exists(contract, client):
                log.error('Reward contracts not setup.')
                return False
        return True

    @staticmethod
    def stamps_in_block(block):
        total = 0

        for sb in block['subblocks']:
            for tx in sb['transactions']:
                total += tx['stamps_used']

        log.info(f'{total} stamps in block #{block["number"]} to issue as rewards.')

        return total

    @staticmethod
    def add_to_balance(vk, amount, client: ContractingClient):
        current_balance = client.get_var(contract='currency', variable='balances', arguments=[vk], mark=False)

        if current_balance is None:
            current_balance = ContractingDecimal(0)

        amount = ContractingDecimal(amount)

        client.set_var(
            contract='currency',
            variable='balances',
            arguments=[vk],
            value=amount + current_balance,
            mark=True
        )

    @staticmethod
    def calculate_participant_reward(participant_ratio, number_of_participants, total_tau_to_split):
        reward = (decimal.Decimal(str(participant_ratio)) / number_of_participants) * decimal.Decimal(str(total_tau_to_split))
        rounded_reward = round(reward, DUST_EXPONENT)
        return rounded_reward

    @staticmethod
    def calculate_all_rewards(total_tau_to_split, client: ContractingClient):
        master_ratio, delegate_ratio, burn_ratio, foundation_ratio = \
            client.get_var(contract='rewards', variable='S', arguments=['value'])

        master_reward = RewardManager.calculate_participant_reward(
            participant_ratio=master_ratio,
            number_of_participants=len(client.get_var(contract='masternodes', variable='S', arguments=['members'])),
            total_tau_to_split=total_tau_to_split
        )

        delegate_reward = RewardManager.calculate_participant_reward(
            participant_ratio=delegate_ratio,
            number_of_participants=len(client.get_var(contract='delegates', variable='S', arguments=['members'])),
            total_tau_to_split=total_tau_to_split
        )

        foundation_reward = RewardManager.calculate_participant_reward(
            participant_ratio=foundation_ratio,
            number_of_participants=1,
            total_tau_to_split=total_tau_to_split
        )

        # burn does nothing, as the stamps are already deducted from supply

        log.info(f'Master reward: {format(master_reward, ".4f")}t per master. '
                 f'Delegate reward: {format(delegate_reward, ".4f")}t per delegate. '
                 f'Foundation reward: {format(foundation_reward, ".4f")}t. '
                 f'Remainder is burned.')

        return master_reward, delegate_reward, foundation_reward

    @staticmethod
    def distribute_rewards(master_reward, delegate_reward, foundation_reward, client: ContractingClient):
        for m in client.get_var(contract='masternodes', variable='S', arguments=['members']):
            RewardManager.add_to_balance(vk=m, amount=master_reward, client=client)

        for d in client.get_var(contract='delegates', variable='S', arguments=['members']):
            RewardManager.add_to_balance(vk=d, amount=delegate_reward, client=client)

        foundation_wallet = client.get_var(contract='foundation', variable='owner')
        RewardManager.add_to_balance(vk=foundation_wallet, amount=foundation_reward, client=client)

    @staticmethod
    def calculate_tau_to_split(block, client: ContractingClient):
        return RewardManager.stamps_in_block(block) / client.get_var(contract='stamp_cost', variable='S', arguments=['value'])

    @staticmethod
    def issue_rewards(block, client: ContractingClient):
        total_tau_to_split = RewardManager.calculate_tau_to_split(block, client)

        rewards = RewardManager.calculate_all_rewards(
            total_tau_to_split=total_tau_to_split,
            client=client
        )

        RewardManager.distribute_rewards(*rewards, client=client)
