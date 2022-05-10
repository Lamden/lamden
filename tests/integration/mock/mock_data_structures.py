from unittest import TestCase
from lamden.crypto.wallet import Wallet
from lamden.nodes.hlc import HLC_Clock

class MockTransaction:
    def __init__(self,
                 metadata: dict = dict(),
                 payload: dict = dict()
                 ):
        self.metadata = metadata
        self.payload = payload

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
                 transaction: MockTransaction = MockTransaction(),
    ):

        self.hash = hash
        self.hlc_timestamp = hlc_timestamp
        self.result = result
        self.stamps_used = stamps_used
        self.state = state
        self.status = status
        self.transaction = transaction

    def set_hlc_timestamp(self, hlc_timestamp):
        self.hlc_timestamp = hlc_timestamp

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



class MockBlock:
    def __init__(self,
                 number: int = 0,
                 hlc_timestamp: str = None,
                 hash: str = 64 * "0",
                 previous: str = 64 * "0",
                 proofs: list = [],
                 processed: MockProcessed = MockProcessed()
    ):

        self.number = number
        self.hlc_timestamp = hlc_timestamp
        self.hash = hash
        self.previous = previous
        self.proofs = proofs
        self.processed = processed

        if hlc_timestamp is None:
            self.hlc_timestamp = self.get_new_hlc()
            self.processed.set_hlc_timestamp(hlc_timestamp=self.hlc_timestamp)

    def get_new_hlc(self):
        hlc_clock = HLC_Clock()
        return hlc_clock.get_new_hlc_timestamp()

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
    def __init__(self, blocks: dict = dict()):
        self.blocks = blocks
        self.block_height = 0

    @property
    def current_block_height(self):
        k = list(self.blocks.keys())
        k.sort()
        try:
            return int(k[0])
        except IndexError:
            return 0

    def add_block(self):
        next_block_number = self.current_block_height + 1
        self.blocks[next_block_number] = MockBlock(number=next_block_number)

class TestMockBlock(TestCase):
    def setUp(self):
        pass

    def tearDown(self):
        pass

    def test_add_block(self):
        blocks = MockBlocks()

        blocks.add_block()

        self.assertEqual(1, blocks.block_height)