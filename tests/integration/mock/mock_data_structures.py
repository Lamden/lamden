from unittest import TestCase
from lamden.crypto.wallet import Wallet
from lamden.nodes.hlc import HLC_Clock
from lamden.crypto.canonical import tx_hash_from_tx, block_from_tx_results
import copy
import json
from contracting.stdlib.bridge.decimal import ContractingDecimal

class MockTransaction:
    def __init__(self,
                 metadata: dict = None,
                 payload: dict = None
                 ):

        self.metadata = metadata
        self.payload = payload

        if self.metadata is None or self.payload is None:
            self.create_default_transaction()

    def create_default_transaction(self):
        sender_wallet = Wallet()
        kwargs = dict({
                    "amount": {"__fixed__": "10.5"},
                    "to": Wallet().verifying_key
                })
        self.create_transaction(
            sender_wallet=sender_wallet,
            contract="currency",
            function="transfer",
            kwargs=kwargs,
            nonce=0,
            processor=Wallet().verifying_key,
            stamps_supplied=20
        )

    def create_transaction(self, sender_wallet: Wallet, contract: str, function: str, kwargs: dict, nonce: int, processor: str,
                           stamps_supplied: int):
        self.payload = dict({
            "sender": sender_wallet.verifying_key,
            "contract": contract,
            "function": function,
            "kwargs": kwargs,
            "nonce": nonce,
            "processor": processor,
            "stamps_supplied": stamps_supplied
        })

        signature = sender_wallet.sign(json.dumps(self.payload))

        self.metadata = dict({'signature': signature})

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
                 hlc_timestamp: str = None,
                 result: any = None,
                 stamps_used: int = 0,
                 state: list = [],
                 status: int = 0,
                 transaction: dict = dict({}),
                 internal_state: dict = None
    ):

        self.hlc_timestamp = hlc_timestamp
        self.result = result
        self.stamps_used = stamps_used
        self.state = copy.copy(state)
        self.status = status
        self.transaction: MockTransaction

        self.transaction = copy.copy(MockTransaction(
            payload=transaction.get('payload'),
            metadata=transaction.get('metadata')
        ))

        if hlc_timestamp is None:
            self.get_new_hlc()

        self.hash = hash or tx_hash_from_tx(self.transaction.as_dict())

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
                    internal_state[to] += amount

                self.state = [{
                    'key': f'currency.balances:{to}',
                    'value': {'__fixed__': str(internal_state[to]) }
                }]

                print (self.state)

    def set_hlc_timestamp(self, hlc_timestamp):
        self.hlc_timestamp = hlc_timestamp

    def get_new_hlc(self):
        hlc_clock = HLC_Clock()
        self.set_hlc_timestamp(hlc_timestamp=hlc_clock.get_new_hlc_timestamp())

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


class MockBlock:
    def __init__(self,
                 number: int = 0,
                 hlc_timestamp: str = None,
                 hash: str = None,
                 previous: str = 64 * "0",
                 proofs: list = [],
                 processed: MockProcessed = None,
                 internal_state: dict = None
    ):

        self.number = number
        self.hash = hash
        self.hlc_timestamp = hlc_timestamp
        self.previous = previous
        self.proofs = proofs
        self.processed = processed or copy.copy(MockProcessed(internal_state=internal_state))

        block = block_from_tx_results(
            processing_results=self.processed.as_dict(),
            proofs=self.proofs,
            block_num=self.number,
            prev_block_hash=self.previous
        )

        if self.hash is None:
            self.hash = block.get('hash')

        if self.hlc_timestamp is None:
            self.hlc_timestamp=block.get('hlc_timestamp')

    def as_dict(self):
        processed = self.processed.as_dict()

        d = dict(self.__dict__)
        d['processed'] = processed
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
        self.assertEqual(6, len(block_dict))

        self.assertEqual(0, block_dict.get('number'))
        self.assertIsNotNone(block_dict.get('hlc_timestamp'))
        self.assertIsInstance(block_dict.get('hlc_timestamp'), str)
        self.assertEqual(64 * "0", block_dict.get('hash'))
        self.assertEqual(64 * "0", block_dict.get('previous'))
        self.assertEqual([], block_dict.get('proofs'))

class MockBlocks:
    def __init__(self, num_of_blocks: int = 0):
        self.blocks = dict()
        self.internal_state = dict()

        if num_of_blocks > 0:
            self.add_blocks(num_of_blocks=num_of_blocks)

    @property
    def current_block_height(self):
        k = list(self.blocks.keys())
        k.sort()
        try:
            return int(k[-1])
        except IndexError:
            return 0

    def add_block(self):
        next_block_number = self.current_block_height + 1
        if next_block_number == 1:
            new_block = copy.copy(MockBlock(
                number=next_block_number,
                internal_state=self.internal_state
            ))
        else:
            previous_block = self.get_block(num=self.current_block_height)
            new_block = copy.copy(MockBlock(
                number=next_block_number,
                previous=previous_block.get("hash"),
                internal_state=self.internal_state
            ))

        self.blocks[next_block_number] = new_block.as_dict()

    def add_blocks(self, num_of_blocks):
        for i in range(num_of_blocks):
            self.add_block()
            print(self.get_block(num=i+1))

    def get_block(self, num: int):
        return self.blocks.get(num)

class TestMockBlock(TestCase):
    def setUp(self):
        pass

    def tearDown(self):
        pass

    def test_add_block(self):
        blocks = MockBlocks()
        blocks.add_block()

        self.assertEqual(1, blocks.current_block_height)


    def test_get_block(self):
        blocks = MockBlocks()
        blocks.add_block()

        block_1 = blocks.get_block(num=1)
        self.assertEqual(1, block_1.number)

    def test_add_blocks(self):
        blocks = MockBlocks()
        blocks.add_blocks(num_of_blocks=5)

        self.assertEqual(5, blocks.current_block_height)