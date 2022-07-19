from unittest import TestCase
from lamden.crypto.wallet import Wallet
from lamden.nodes.hlc import HLC_Clock
from lamden.crypto.canonical import tx_hash_from_tx, block_from_tx_results, block_hash_from_block, tx_result_hash_from_tx_result_object
import copy
import json
from contracting.stdlib.bridge.decimal import ContractingDecimal
from lamden.crypto.transaction import build_transaction

class MockTransaction:
    __sender_wallet = Wallet()
    __processor_wallet = Wallet()

    def __init__(self,
                 metadata: dict = None,
                 payload: dict = None
                 ):

        self.metadata = metadata
        self.payload = payload

        if self.metadata is None or self.payload is None:
            self.create_default_transaction()

    def create_default_transaction(self):
        kwargs = dict({
                    "amount": {"__fixed__": "10.5"},
                    "to": Wallet().verifying_key
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
                 internal_state: dict = None
    ):
        '''
        "hash": "bedbf2872cf337c40408d3b17f1ed649af173e812156d7066ccabc8cda26ad4a",
        "result": "None",
        "stamps_used": 1,
        "state": [
            {
                "key": "currency.balances:3515aa7b15d7b97855a0266935bf26c44ad8d8198b2dc81ce035ba1b86b0f340",
                "value": {
                    "__fixed__": "50"
                }
            },
            {
                "key": "currency.balances:c0006724aa6fc81619b7e27816e69ab824ad04d39640bb87fb86720f452a1ed5",
                "value": {
                    "__fixed__": "499900"
                }
            }
        ],
        "status": 0,
        "transaction": TRANSACTION
        '''

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
                    internal_state[to] += amount

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


class MockBlock:
    def __init__(self,
                 number: int = 0,
                 hlc_timestamp: str = None,
                 previous: str = 64 * "0",
                 proofs: list = [],
                 rewards: list = [],
                 internal_state: dict = None
    ):

        if not hlc_timestamp:
            self.get_new_hlc()

        self.number = number
        self.previous = previous
        self.proofs = proofs

        block_hash = block_hash_from_block(
            hlc_timestamp=self.hlc_timestamp,
            block_number=self.number,
            previous_block_hash=self.previous
        )

        self.hash = block_hash

        mock_processed = copy.copy(MockProcessed(internal_state=internal_state, hlc_timestamp=self.hlc_timestamp))
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
            new_block = copy.deepcopy(MockBlock(
                number=next_block_number,
                internal_state=self.internal_state
            ))
        else:
            previous_block = self.get_block(num=self.current_block_height)
            new_block = copy.deepcopy(MockBlock(
                number=next_block_number,
                previous=previous_block.get("hash"),
                internal_state=self.internal_state
            ))
        new_block.add_proofs(amount_to_add=3)
        self.blocks[next_block_number] = dict(new_block.as_dict())

    def add_blocks(self, num_of_blocks):
        for i in range(num_of_blocks):
            self.add_block()
            print(self.get_block(num=i+1))

    def get_block(self, num: int):
        return self.blocks.get(num)

    def get_latest_block(self):
        return self.get_block(num=self.current_block_height)

class TestMockBlocks(TestCase):
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