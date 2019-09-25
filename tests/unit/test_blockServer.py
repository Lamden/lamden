from unittest import TestCase
from cilantro_ee.services.block_server import BlockServer, block_dictionary_to_block_struct, block_struct_to_block_dictionary
from cilantro_ee.storage.master import MasterStorage, CilantroStorageDriver
from tests import random_txs
from cilantro_ee.protocol.wallet import Wallet


class TestBlockServer(TestCase):
    def test_block_dictionary_to_block_struct(self):
        block = random_txs.random_block()
        # block_store = CilantroStorageDriver(key=Wallet().sk.encode().hex())
        #
        # b = block_store.store_block([sb for sb in block.subBlocks])
        block_dict = block_struct_to_block_dictionary(block)
        block_struct = block_dictionary_to_block_struct(block_dict)

        self.assertEqual(block.to_dict(), block_struct)