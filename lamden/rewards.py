import decimal
from collections import defaultdict

from contracting.stdlib.bridge.decimal import ContractingDecimal
from contracting.client import ContractingClient

from lamden.logger.base import get_logger

decimal.getcontext().rounding = decimal.ROUND_DOWN

REQUIRED_CONTRACTS = [
    'stamp_cost',
    'rewards',
    'currency',
    'election_house',
    'foundation',
    'masternodes'
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
    def add_to_balance(vk, amount, client: ContractingClient):
        current_balance = client.get_var(contract='currency', variable='balances', arguments=[vk], mark=False)

        if type(current_balance) is dict:
            current_balance = ContractingDecimal(current_balance.get('__fixed__'))

        if current_balance is None:
            current_balance = ContractingDecimal(0)

        amount = ContractingDecimal(amount)

        new_balance = amount + current_balance

        client.set_var(
            contract='currency',
            variable='balances',
            arguments=[vk],
            value=new_balance,
            mark=True
        )

        return {
            'key': f'currency.balances:{vk}',
            'value': new_balance,
            'reward': amount
        }

    @staticmethod
    def calculate_participant_reward(participant_ratio, number_of_participants, total_stamps_to_split):
        number_of_participants = number_of_participants if number_of_participants != 0 else 1
        reward = (decimal.Decimal(str(participant_ratio)) / number_of_participants) * decimal.Decimal(str(total_stamps_to_split))
        rounded_reward = round(reward, DUST_EXPONENT)
        return rounded_reward

    @staticmethod
    def calculate_tx_output_rewards(total_stamps_to_split, contract, client: ContractingClient):

        try:
            master_ratio, burn_ratio, foundation_ratio, developer_ratio = \
                client.get_var(contract='rewards', variable='S', arguments=['value'])
        except TypeError:
            raise NotImplementedError("Driver could not get value for key rewards.S:value. Try setting up rewards.")

        master_reward = RewardManager.calculate_participant_reward(
            participant_ratio=master_ratio,
            number_of_participants=len(client.get_var(contract='masternodes', variable='S', arguments=['members'])),
            total_stamps_to_split=total_stamps_to_split
        )

        foundation_reward = RewardManager.calculate_participant_reward(
            participant_ratio=foundation_ratio,
            number_of_participants=1,
            total_stamps_to_split=total_stamps_to_split
        )

        developer_mapping = RewardManager.find_developer_and_reward(
            total_stamps_to_split=total_stamps_to_split, contract=contract, client=client, developer_ratio=developer_ratio
        )

        return master_reward, foundation_reward, developer_mapping

    @staticmethod
    def find_developer_and_reward(total_stamps_to_split, contract: str, developer_ratio, client: ContractingClient):
        # Find all transactions and the developer of the contract.
        # Count all stamps used by people and multiply it by the developer ratio
        send_map = defaultdict(lambda: 0)

        recipient = client.get_var(
            contract=contract,
            variable='__developer__'
        )

        send_map[recipient] += (total_stamps_to_split * developer_ratio)
        send_map[recipient] /= len(send_map)

        return send_map

    @staticmethod
    def distribute_rewards(master_reward, foundation_reward, developer_mapping, client: ContractingClient) -> list:
        stamp_cost = client.get_var(contract='stamp_cost', variable='S', arguments=['value'])

        master_reward /= stamp_cost
        foundation_reward /= stamp_cost

        rewards = []

        for m in client.get_var(contract='masternodes', variable='S', arguments=['members']):
            rewards.append(RewardManager.add_to_balance(vk=m, amount=master_reward, client=client))

        foundation_wallet = client.get_var(contract='foundation', variable='owner')
        rewards.append(RewardManager.add_to_balance(vk=foundation_wallet, amount=foundation_reward, client=client))

        # Send rewards to each developer calculated from the block
        for recipient, amount in developer_mapping.items():
            dev_reward = round((amount / stamp_cost), DUST_EXPONENT)
            rewards.append(RewardManager.add_to_balance(vk=recipient, amount=dev_reward, client=client))

        # Remainder is BURNED

        try:
            rewards.sort(key=lambda x: x['key'])
        except Exception as err:
            print("Unable to sort rewards by 'key'.")
            print(err)

        return rewards
