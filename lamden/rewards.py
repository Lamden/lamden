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

        # log.info(f'{total} stamps in block #{block["number"]} to issue as rewards.')

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
    def calculate_participant_reward(participant_ratio, number_of_participants, total_stamps_to_split):
        reward = (decimal.Decimal(str(participant_ratio)) / number_of_participants) * decimal.Decimal(str(total_stamps_to_split))
        rounded_reward = round(reward, DUST_EXPONENT)
        return rounded_reward

    @staticmethod
    def calculate_all_rewards(block, client: ContractingClient):
        total_stamps_to_split = RewardManager.stamps_in_block(block)

        master_ratio, delegate_ratio, burn_ratio, foundation_ratio, developer_ratio = \
            client.get_var(contract='rewards', variable='S', arguments=['value'])

        master_reward = RewardManager.calculate_participant_reward(
            participant_ratio=master_ratio,
            number_of_participants=len(client.get_var(contract='masternodes', variable='S', arguments=['members'])),
            total_stamps_to_split=total_stamps_to_split
        )

        delegate_reward = RewardManager.calculate_participant_reward(
            participant_ratio=delegate_ratio,
            number_of_participants=len(client.get_var(contract='delegates', variable='S', arguments=['members'])),
            total_stamps_to_split=total_stamps_to_split
        )

        foundation_reward = RewardManager.calculate_participant_reward(
            participant_ratio=foundation_ratio,
            number_of_participants=1,
            total_stamps_to_split=total_stamps_to_split
        )

        developer_mapping = RewardManager.create_to_send_map(block=block, client=client, developer_ratio=developer_ratio)

        # burn does nothing, as the stamps are already deducted from supply

        return master_reward, delegate_reward, foundation_reward, developer_mapping

    @staticmethod
    def distribute_rewards(master_reward, delegate_reward, foundation_reward, developer_mapping, client: ContractingClient):
        stamp_cost = client.get_var(contract='stamp_cost', variable='S', arguments=['value'])

        master_reward /= stamp_cost
        delegate_reward /= stamp_cost
        foundation_reward /= stamp_cost
        '''
        log.info(f'Master reward: {format(master_reward, ".4f")}t per master. '
                 f'Delegate reward: {format(delegate_reward, ".4f")}t per delegate. '
                 f'Foundation reward: {format(foundation_reward, ".4f")}t.')
        '''
        for m in client.get_var(contract='masternodes', variable='S', arguments=['members']):
            RewardManager.add_to_balance(vk=m, amount=master_reward, client=client)

        for d in client.get_var(contract='delegates', variable='S', arguments=['members']):
            RewardManager.add_to_balance(vk=d, amount=delegate_reward, client=client)

        foundation_wallet = client.get_var(contract='foundation', variable='owner')
        RewardManager.add_to_balance(vk=foundation_wallet, amount=foundation_reward, client=client)

        # Send rewards to each developer calculated from the block
        for recipient, amount in developer_mapping.items():
            dev_reward = round((amount / stamp_cost), DUST_EXPONENT)
            RewardManager.add_to_balance(vk=recipient, amount=dev_reward, client=client)

        # log.info(f'Remainder is burned.')

    @staticmethod
    def issue_rewards(block, client: ContractingClient):
        rewards = RewardManager.calculate_all_rewards(
            client=client,
            block=block
        )

        RewardManager.distribute_rewards(*rewards, client=client)

    @staticmethod
    def create_to_send_map(block, developer_ratio, client: ContractingClient):
        # Find all transactions and the developer of the contract.
        # Count all stamps used by people and multiply it by the developer ratio
        send_map = defaultdict(lambda: 0)

        for sb in block['subblocks']:
            for tx in sb['transactions']:
                contract = tx['transaction']['payload']['contract']

                recipient = client.get_var(
                    contract=contract,
                    variable='__developer__'
                )

                send_map[recipient] += (tx['stamps_used'] * developer_ratio)

        for developer in send_map.keys():
            send_map[developer] /= len(send_map)

        return send_map
