from unittest import TestCase
from cilantro_ee.storage.master import CilantroStorageDriver
from cilantro_ee.protocol import wallet
from cilantro_ee.messages.block_data.sub_block import SubBlockBuilder


class TestCilantroStorageDriver(TestCase):
    def setUp(self):
        sk, vk = wallet.new()
        self.db = CilantroStorageDriver(key=sk)

    def tearDown(self):
        self.db.drop_collections()

    def test_init(self):
        self.assertIsNotNone(self.db)

    def test_store_block(self):
        sub_blocks = [SubBlockBuilder.create(idx=i) for i in range(10)]

        self.assertIsNone(self.db.get_block(1))

        self.db.store_block(sub_blocks)

        block = self.db.get_block(1)

        self.assertIsNotNone(block)

        owners = block['blockOwners']

        self.assertEqual(owners, self.db.vkbook.masternodes)
