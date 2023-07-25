from unittest import TestCase
from lamden.crypto.wallet import Wallet
from lamden.nodes.hlc import HLC_Clock
from lamden.crypto.canonical import create_proof_message_from_tx_results, tx_hash_from_tx, hash_genesis_block_state_changes, block_hash_from_block, tx_result_hash_from_tx_result_object
import copy
import json
from contracting.stdlib.bridge.decimal import ContractingDecimal
from contracting.db.encoder import decode, encode
from lamden.crypto.transaction import build_transaction
from lamden.crypto.block_validator import verify_block
from lamden.utils import hlc, create_genesis
from lamden.crypto.wallet import verify
from copy import deepcopy
from lamden.crypto.block_validator import GENESIS_BLOCK_NUMBER

class MockTransaction:
    __sender_wallet = Wallet()
    __processor_wallet = Wallet()

    def __init__(self,
                 metadata: dict = None,
                 payload: dict = None,
                 receiver_wallet: Wallet = None,
                 add_members: bool = False
                 ):

        self.metadata = metadata
        self.payload = payload

        if self.metadata is None or self.payload is None:
            if add_members:
                self.create_add_members_transaction()
            else:
                self.create_default_transaction(receiver_wallet=receiver_wallet)

    def create_default_transaction(self, receiver_wallet: Wallet = None):
        to = Wallet().verifying_key
        if receiver_wallet is not None:
            to = receiver_wallet.verifying_key
        kwargs = dict({
                    "amount": {"__fixed__": "10.5"},
                    "to": to
                })
        self.create_transaction(
            sender_wallet=self.__class__.__sender_wallet,
            contract="currency",
            function="transfer",
            kwargs=kwargs,
            nonce=0,
            processor=self.__class__.__processor_wallet.verifying_key,
            stamps_supplied=20
        )

    def create_add_members_transaction(self):
        kwargs = dict({
            "policy": "masternodes",
            "value": ["introduce_motion", 2]
        })
        self.create_transaction(
            sender_wallet=self.__class__.__sender_wallet,
            contract="election_house",
            function="vote",
            kwargs=kwargs,
            nonce=0,
            processor=self.__class__.__processor_wallet.verifying_key,
            stamps_supplied=20
        )

    def create_transaction(self, sender_wallet: Wallet, contract: str, function: str, kwargs: dict, nonce: int, processor: str,
                           stamps_supplied: int):
        str_tx = build_transaction(
            wallet=sender_wallet,
            contract=contract,
            function=function,
            kwargs=kwargs,
            nonce=nonce,
            processor=processor,
            stamps=stamps_supplied
        )

        tx_obj = json.loads(str_tx)

        self.metadata = tx_obj.get('metadata')
        self.payload = tx_obj.get('payload')

    def get_processor(self):
        return self.payload.get('processor')

    def get_processor_wallet(self):
        return self.__class__.__processor_wallet

    def as_dict(self):
        return dict(self.__dict__)

class TestMockTransaction(TestCase):
    def setUp(self):
        pass

    def tearDown(self):
        pass

    def test_default_return(self):
        tx = MockTransaction()
        self.assertEqual({}, tx.metadata)
        self.assertEqual({}, tx.payload)

class MockProcessed:
    def __init__(self,
                 hash: str = None,
                 hlc_timestamp: str = "",
                 result: any = 'None',
                 stamps_used: int = 0,
                 state: list = [],
                 status: int = 0,
                 transaction: dict = dict({}),
                 internal_state: dict = None,
                 one_wallet: bool = False,
                 members_list: list = None
    ):

        self.result = result
        self.stamps_used = stamps_used
        self.state = copy.copy(state)
        self.status = status

        self.transaction: MockTransaction

        if members_list is not None:
            self.transaction = copy.copy(MockTransaction(
                add_members=True
            ))
        else:
            self.transaction = copy.copy(MockTransaction(
                payload=transaction.get('payload'),
                metadata=transaction.get('metadata'),
                add_members=members_list is not None
            ))

        self.hash = hash or tx_hash_from_tx(self.transaction.as_dict())

        processor_wallet = self.transaction.get_processor_wallet()

        self.tx_message = {
            'sender': processor_wallet.verifying_key,
            'signature': processor_wallet.sign(f'{self.hash}{hlc_timestamp}')
        }

        if internal_state is not None:
            contract = self.transaction.payload.get('contract')
            function = self.transaction.payload.get('function')
            if contract == 'currency' and function == 'transfer':
                kwargs = self.transaction.payload.get('kwargs')
                to = kwargs.get('to')
                amount = kwargs.get('amount')
                key = f'currency.balances:{to}'
                if amount.get('__fixed__') is not None:
                    amount = amount.get('__fixed__')

                current_bal = internal_state.get(key)

                if current_bal is None:
                    internal_state[key] = ContractingDecimal(amount)
                else:
                    internal_state[key] += ContractingDecimal(amount)

                self.state = [{
                    'key': key,
                    'value': internal_state[key]
                }]

        if members_list is not None:
            self.state = [{
                'key': 'masternodes.S:members',
                'value': members_list
            }]

    def as_dict(self):
        transaction = dict(self.transaction.__dict__)
        d = dict(self.__dict__)
        d['transaction'] = transaction
        return d


class TestMockProcessed(TestCase):
    def setUp(self):
        pass

    def tearDown(self):
        pass

    def test_as_dict(self):
        processed = MockProcessed()
        self.assertIsInstance(processed.transaction, MockTransaction)

        processed_dict = processed.as_dict()

        self.assertEqual(7, len(processed_dict))

        self.assertEqual(None, processed_dict.get('hash'))
        self.assertEqual(None, processed_dict.get('hlc_timestamp'))
        self.assertEqual(None, processed_dict.get('result'))
        self.assertEqual(0, processed_dict.get('stamps_used'))
        self.assertEqual([], processed_dict.get('state'))
        self.assertEqual(0, processed_dict.get('status'))

    def test_creates_hash_from_tx_info(self):
        processed = MockProcessed()

        self.assertNotEqual(64 * '0', processed.hash)

class MockGenesisBlock:
    def __init__(self, internal_state: dict = {}, founder_wallet: Wallet = Wallet(), initial_members: dict = {}):

        self.founder_wallet = founder_wallet
        internal_state.update({'masternodes.S:members': initial_members.get('masternodes', [])})
        internal_state.update({f'currency.balances:{founder_wallet.verifying_key}': 100000000})
        self.block = create_genesis.build_block(
            founder_sk=founder_wallet.signing_key,
            additional_state=internal_state,
            initial_members=initial_members
        )

        self.hlc_timestamp = self.block['hlc_timestamp']
        self.number = str(hlc.nanos_from_hlc_timestamp(hlc_timestamp=self.hlc_timestamp))
        self.previous = self.block['previous']
        self.origin = self.block['origin']
        self.genesis = self.block['genesis']

    def as_dict(self):
        return self.block

class TestMockGenesisBlock(TestCase):
    def setUp(self):
        pass

    def tearDown(self):
        pass

    def test_creates_genesis_block(self):
        mock_gen_block = MockGenesisBlock()
        block_dict = mock_gen_block.as_dict()

        self.assertEqual('0', block_dict.get('number'))
        self.assertEqual('0000-00-00T00:00:00.000000000Z_0', block_dict.get('hlc_timestamp'))
        self.assertEqual('0' * 64, block_dict.get('previous'))

        sender = block_dict['origin'].get('sender')
        self.assertEqual(sender, mock_gen_block.founder_wallet.verifying_key)

        message = hash_genesis_block_state_changes(state_changes=block_dict.get('genesis'))
        signature = block_dict['origin'].get('signature')

        self.assertTrue(verify(
            vk=sender,
            msg=message,
            signature=signature
        ))

        self.assertEqual(6, len(block_dict))

class MockBlock:
    def __init__(self,
                 hlc_timestamp: str = None,
                 previous: str = 64 * "0",
                 rewards: list = [],
                 internal_state: dict = None,
                 receiver_wallet: Wallet = None,
                 member_wallets: list = [],
                 masternode_wallet: Wallet = Wallet(),
                 members_list: list = None
    ):

        if not hlc_timestamp:
            self.get_new_hlc()

        if len(member_wallets) == 0:
            member_wallets = [Wallet(), Wallet(), masternode_wallet]

        self.number = str(hlc.nanos_from_hlc_timestamp(hlc_timestamp=self.hlc_timestamp))
        self.previous = previous

        block_hash = block_hash_from_block(
            hlc_timestamp=self.hlc_timestamp,
            block_number=self.number,
            previous_block_hash=self.previous
        )

        self.hash = block_hash

        if receiver_wallet:
            mock_transaction = copy.copy(MockTransaction(
                receiver_wallet=receiver_wallet
            ))
            mock_processed = copy.copy(MockProcessed(
                internal_state=internal_state,
                hlc_timestamp=self.hlc_timestamp,
                transaction=mock_transaction.as_dict()
            ))
        else:
            if members_list is not None:
                mock_processed = copy.copy(MockProcessed(
                    internal_state=internal_state,
                    hlc_timestamp=self.hlc_timestamp,
                    members_list=members_list
                ))
            else:
                mock_processed = copy.copy(MockProcessed(
                    internal_state=internal_state,
                    hlc_timestamp=self.hlc_timestamp
                ))
        self.origin = dict(mock_processed.tx_message)

        del mock_processed.tx_message

        self.rewards = rewards

        self.processed = mock_processed.as_dict()

        self.proofs = self.create_proofs(
            tx_result=mock_processed.as_dict(),
            hlc_timestamp=self.hlc_timestamp,
            rewards=self.rewards,
            member_wallets=member_wallets
        )

    def get_new_hlc(self):
        hlc_clock = HLC_Clock()
        self.set_hlc_timestamp(hlc_timestamp=hlc_clock.get_new_hlc_timestamp())

    def set_hlc_timestamp(self, hlc_timestamp):
        self.hlc_timestamp = hlc_timestamp

    def create_proofs(self, tx_result, hlc_timestamp, rewards, member_wallets):
        proofs = list()

        members_list = [member_wallet.verifying_key for member_wallet in member_wallets]

        for member_wallet in member_wallets:
            proof_details = create_proof_message_from_tx_results(
                tx_result=tx_result,
                hlc_timestamp=hlc_timestamp,
                rewards=rewards,
                members=members_list,
            )

            signature = member_wallet.sign(proof_details.get('message'))

            proof = {
                'signature': signature,
                'signer': member_wallet.verifying_key,
                'members_list_hash': proof_details.get('members_list_hash'),
                'num_of_members': proof_details.get('num_of_members'),
            }

            proofs.append(proof)

        return proofs

    def add_minted_property(self, minted):
        self.minted = minted

    def as_dict(self):
        d = dict(self.__dict__)
        return d


class TestMockBlock(TestCase):
    def setUp(self):
        pass

    def tearDown(self):
        pass

    def test_as_dict(self):
        masternode_wallet = Wallet()
        block = MockBlock(masternode_wallet=masternode_wallet)

        signature = masternode_wallet.sign(encode(deepcopy(block.as_dict())))
        minted = {
            'minter': masternode_wallet.verifying_key,
            'signature': signature
        }

        block.add_minted_property(minted=minted)
        block_dict = block.as_dict()

        self.assertTrue(verify_block(block=block_dict))



class MockBlocks:
    def __init__(self, num_of_blocks: int = 0, one_wallet: bool = False, initial_members: dict = None,
                 founder_wallet: Wallet = None, masternode_wallet: Wallet = None):
        self.blocks = dict()
        self.internal_state = dict()
        self.founder_wallet = founder_wallet or Wallet()
        self.masternode_wallet = masternode_wallet or Wallet()

        self.member_wallets = initial_members

        if self.member_wallets is None:
            self.member_wallets = [Wallet() for _ in range(3)]

        self.member_wallets.append(self.masternode_wallet)

        self.initial_members = {
            'masternodes': []
        }

        for wallet in self.member_wallets:
            self.initial_members['masternodes'].append(wallet.verifying_key)

        self.receiver_wallet = None
        if one_wallet:
            self.receiver_wallet = Wallet()

        if num_of_blocks > 0:
            self.add_blocks(num_of_blocks=num_of_blocks)

    @property
    def current_block_height(self):
        k = list(self.blocks.keys())
        k.sort()
        try:
            return int(k[-1])
        except IndexError:
            return -1

    @property
    def total_blocks(self):
        k = list(self.blocks.keys())
        return len(k)

    @property
    def block_numbers_list(self):
        block_numbers = [block_num for block_num in self.blocks.keys()]
        block_numbers.sort()
        return block_numbers

    @property
    def block_list(self):
        blocks = [block for block in list(self.blocks.values())]
        blocks = sorted(blocks, key=lambda x: int(x['number']))
        return blocks

    @property
    def block_list_encoded(self):
        blocks = [json.loads(encode(block)) for block in list(self.blocks.values())]
        blocks = sorted(blocks, key=lambda x: int(x['number']))
        return blocks

    @property
    def latest_block_num(self):
        k = list(self.blocks.keys())
        k.sort()
        try:
            block = self.blocks.get(k[-1])
            return int(block.get('number'))
        except IndexError:
            return -1

    @property
    def latest_hlc_timestamp(self):
        k = list(self.blocks.keys())
        k.sort()
        try:
            block = self.blocks.get(k[-1])
            return block.get('hlc_timestamp')
        except IndexError:
            return ""

    @property
    def latest_block(self):
        k = list(self.blocks.keys())
        k.sort()
        try:
            last_item = k[-1]
            block = self.blocks.get(last_item)
            return block
        except IndexError:
            return None

    @property
    def latest_block_number(self):
        k = list(self.blocks.keys())
        k.sort()
        try:
            return k[-1]
        except IndexError:
            return None

    @property
    def members_list(self):
        gen_block = self.block_list[0]

        for sc in gen_block.get('genesis'):
            if sc.get('key') == 'masternodes.S:members':
                return sc.get('value')

        return []

    def add_block(self, member_wallets: list = None):
        if self.current_block_height == -1:
            new_block =  copy.deepcopy(MockGenesisBlock(
                founder_wallet=self.founder_wallet,
                internal_state=self.internal_state,
                initial_members=self.initial_members
            ))

            for state_change in new_block.block['genesis']:
                self.internal_state[state_change.get('key')] = state_change.get('value')
        else:
            previous_block = self.get_block(num=self.current_block_height)

            members_list = None
            if member_wallets is not None:
                members_list = [wallet.verifying_key for wallet in member_wallets]

            new_block = copy.deepcopy(MockBlock(
                previous=previous_block.get("hash"),
                receiver_wallet=self.receiver_wallet,
                internal_state=self.internal_state,
                member_wallets=self.member_wallets,
                members_list=members_list
            ))
            new_block.add_minted_property(minted=self.create_minted(block=new_block))

            for state_change in new_block.processed.get('state'):
                self.internal_state[state_change.get('key')] = state_change.get('value')

            if member_wallets is not None:
                self.member_wallets = member_wallets

        block_dict = self.add_to_blocks_dict(block=new_block)
        return block_dict

    def add_to_blocks_dict(self, block):
        block_dict = block
        if not isinstance(block_dict, dict):
            block_dict = dict(block.as_dict())

        self.blocks[str(block.number)] = dict(block.as_dict())
        return block_dict

    def add_blocks(self, num_of_blocks):
        for i in range(num_of_blocks):
            block = self.add_block()

    def get_block(self, num: str):
        return self.blocks.get(str(num))

    def get_block_by_index(self, index: int):
        block_list = [self.get_block(num=block_num) for block_num in self.blocks.keys()]
        block_list.sort(key=lambda x: x.get('number'))
        return block_list[index]

    def get_previous_block(self, block_num: int, block_list: list = None):
        if block_list:
            bl = block_list
        else:
            bl = self.block_list

        for index, block in enumerate(bl):
            if int(block.get('number', '-1')) == int(block_num):
                if index == 0:
                    return None
                else:
                    return bl[index - 1]

    def get_latest_block(self):
        return self.get_block(num=self.current_block_height)

    def get_blocks(self):
        blocks = [value for key, value in self.blocks.items()]
        blocks.sort(key=lambda x: x.get('number'))
        return blocks

    def save_members(self, members_list):
        self.initial_members['masternodes'] = members_list

    def create_minted(self, block):
        signature = self.masternode_wallet.sign(encode(deepcopy(block.as_dict())))
        return {
            'minter': self.masternode_wallet.verifying_key,
            'signature': signature
        }

class TestMockBlocks(TestCase):
    def setUp(self):
        pass

    def tearDown(self):
        pass

    def test_add_block(self):
        blocks = MockBlocks()
        blocks.add_block()

        self.assertEqual(0, blocks.current_block_height)
        self.assertEqual(1, blocks.total_blocks)

    def test_get_block(self):
        blocks = MockBlocks()
        blocks.add_block()

        block_1 = blocks.get_block(num=0)
        self.assertEqual('0', block_1.get('number'))

    def test_add_blocks(self):
        blocks = MockBlocks()
        blocks.add_blocks(num_of_blocks=5)

        self.assertEqual(5, blocks.total_blocks)

    def test_block_passes_verify(self):
        blocks = MockBlocks()
        blocks.add_blocks(num_of_blocks=5)

        for block in blocks.block_list:
            self.assertTrue(verify_block(block=block))


