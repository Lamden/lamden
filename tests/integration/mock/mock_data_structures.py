from unittest import TestCase
from lamden.crypto.wallet import Wallet
from lamden.nodes.hlc import HLC_Clock
from lamden.crypto.canonical import tx_hash_from_tx, hash_genesis_block_state_changes, block_hash_from_block, tx_result_hash_from_tx_result_object
import copy
import json
from contracting.stdlib.bridge.decimal import ContractingDecimal
from lamden.crypto.transaction import build_transaction
from lamden.utils import hlc
from lamden.crypto.wallet import verify
from lamden.crypto.block_validator import GENESIS_BLOCK_NUMBER

class MockTransaction:
    __sender_wallet = Wallet()
    __processor_wallet = Wallet()

    def __init__(self,
                 metadata: dict = None,
                 payload: dict = None,
                 receiver_wallet: Wallet = None
                 ):

        self.metadata = metadata
        self.payload = payload

        if self.metadata is None or self.payload is None:
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
                 one_wallet: bool = False
    ):

        self.result = result
        self.stamps_used = stamps_used
        self.state = copy.copy(state)
        self.status = status
        self.transaction: MockTransaction

        self.transaction = copy.copy(MockTransaction(
            payload=transaction.get('payload'),
            metadata=transaction.get('metadata')
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
                if amount.get('__fixed__') is not None:
                    amount = amount.get('__fixed__')

                current_bal = internal_state.get(to)

                if current_bal is None:
                    internal_state[to] = ContractingDecimal(amount)
                else:
                    internal_state[to] += ContractingDecimal(amount)

                self.state = [{
                    'key': f'currency.balances:{to}',
                    'value': {'__fixed__': str(internal_state[to]) }
                }]

                print (self.state)

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
    def __init__(self,
            internal_state: dict = {},
            founder_wallet: Wallet = Wallet()
        ):

        self.hlc_timestamp = '0000-00-00T00:00:00.000000000Z_0'
        self.number = str(hlc.nanos_from_hlc_timestamp(hlc_timestamp=self.hlc_timestamp))
        self.previous = 64 * "0"
        self.origin = {}
        self.genesis = []
        self.founder_wallet = founder_wallet

        self.add_to_genesis(
            key=f'currency.balances:{self.founder_wallet.verifying_key}',
            value=100000000
        )

        for key, value in internal_state.items():
            self.add_to_genesis(key=key, value=value)

        self.genesis.sort(key=lambda x: x.get('key'))

        self.create_origin(signer_wallet=self.founder_wallet)

        self.hash = block_hash_from_block(
            hlc_timestamp=self.hlc_timestamp,
            block_number=self.number,
            previous_block_hash=self.previous
        )

    def create_origin(self, signer_wallet: Wallet):
        state_changes_hash = hash_genesis_block_state_changes(state_changes=self.genesis)
        self.origin = {
            'sender': signer_wallet.verifying_key,
            'signature': signer_wallet.sign(msg=state_changes_hash)
        }

    def add_to_genesis(self, key: str, value: any):
        self.genesis.append({
                'key': key,
                'value': value
            })

    def as_dict(self):
        return dict({
            'hash': self.hash,
            'number': self.number,
            'hlc_timestamp': self.hlc_timestamp,
            'previous': self.previous,
            'genesis': self.genesis,
            'origin': self.origin
        })

class TestMockGenesisBlock(TestCase):
    def setUp(self):
        pass

    def tearDown(self):
        pass

    def test_creates_genesis_block(self):
        mock_gen_block = MockGenesisBlock()
        block_dict = mock_gen_block.as_dict()

        self.assertEqual(0, block_dict.get('number'))
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

        self.assertEqual(5, len(block_dict))

class MockBlock:
    def __init__(self,
                 hlc_timestamp: str = None,
                 previous: str = 64 * "0",
                 proofs: list = [],
                 rewards: list = [],
                 internal_state: dict = None,
                 receiver_wallet: Wallet = None
    ):

        if not hlc_timestamp:
            self.get_new_hlc()

        self.number = str(hlc.nanos_from_hlc_timestamp(hlc_timestamp=self.hlc_timestamp))
        self.previous = previous
        self.proofs = proofs

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
            mock_processed = copy.copy(MockProcessed(
                internal_state=internal_state,
                hlc_timestamp=self.hlc_timestamp
            ))
        self.origin = dict(mock_processed.tx_message)

        del mock_processed.tx_message

        self.rewards = rewards

        self.processed = mock_processed.as_dict()

    def get_new_hlc(self):
        hlc_clock = HLC_Clock()
        self.set_hlc_timestamp(hlc_timestamp=hlc_clock.get_new_hlc_timestamp())

    def set_hlc_timestamp(self, hlc_timestamp):
        self.hlc_timestamp = hlc_timestamp

    def add_proofs(self, amount_to_add: int = 1):
        if not self.processed:
            return

        for i in range(amount_to_add):
            tx_result_hash = tx_result_hash_from_tx_result_object(
                tx_result=self.processed,
                hlc_timestamp=self.hlc_timestamp,
                rewards=self.rewards
            )

            wallet = Wallet()
            proof = {
                'signer': wallet.verifying_key,
                'signature': wallet.sign(msg=tx_result_hash)
            }
            self.proofs.append(proof)

    def as_dict(self):
        d = dict(self.__dict__)
        return d


class TestMockBlock(TestCase):
    def setUp(self):
        pass

    def tearDown(self):
        pass

    def test_as_dict(self):
        block = MockBlock()
        self.assertIsInstance(block.processed, MockProcessed)

        block_dict = block.as_dict()
        self.assertEqual(8, len(block_dict))

        self.assertEqual(0, block_dict.get('number'))
        self.assertIsNotNone(block_dict.get('hlc_timestamp'))
        self.assertIsInstance(block_dict.get('hlc_timestamp'), str)
        self.assertEqual(64, len(block_dict.get('hash')))
        self.assertEqual(64 * "0", block_dict.get('previous'))
        self.assertEqual([], block_dict.get('proofs'))
        self.assertEqual([], block_dict.get('rewards'))

class MockBlocks:
    def __init__(self, num_of_blocks: int = 0, one_wallet: bool = False):
        self.blocks = dict()
        self.internal_state = dict()
        self.founder_wallet = Wallet()

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
            return int(self.blocks.get(k[-1]))
        except IndexError:
            return None

    def add_block(self):
        if self.current_block_height == -1:
            new_block =  copy.deepcopy(MockGenesisBlock(
                founder_wallet=self.founder_wallet,
                internal_state=self.internal_state
            ))

            for state_change in new_block.genesis:
                self.internal_state[state_change.get('key')] = state_change.get('value')
        else:
            previous_block = self.get_block(num=self.current_block_height)
            new_block = copy.deepcopy(MockBlock(
                previous=previous_block.get("hash"),
                receiver_wallet=self.receiver_wallet,
                internal_state=self.internal_state
            ))
            new_block.add_proofs(amount_to_add=3)

            for state_change in new_block.processed.get('state'):
                self.internal_state[state_change.get('key')] = state_change.get('value')

        block_dict = dict(new_block.as_dict())
        self.blocks[new_block.number] = dict(new_block.as_dict())
        return block_dict

    def add_blocks(self, num_of_blocks):
        for i in range(num_of_blocks):
            block = self.add_block()
            print(block)

    def get_block(self, num: str):
        return self.blocks.get(str(num))

    def get_block_by_index(self, index: int):
        block_list = [self.get_block(num=block_num) for block_num in self.blocks.keys()]
        block_list.sort(key=lambda x: x.get('number'))
        return block_list[index]

    def get_latest_block(self):
        return self.get_block(num=self.current_block_height)

    def get_blocks(self):
        blocks = [value for key, value in self.blocks.items()]
        blocks.sort(key=lambda x: x.get('number'))
        return blocks

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
        self.assertEqual(0, block_1.get('number'))

    def test_add_blocks(self):
        blocks = MockBlocks()
        blocks.add_blocks(num_of_blocks=5)

        self.assertEqual(5, blocks.total_blocks)