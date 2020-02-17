from unittest import TestCase
from cilantro_ee.crypto import canonical
from tests import random_txs


class TestCanonicalCoding(TestCase):
    def test_recursive_dictionary_sort_works(self):
        unsorted = {
            'z': 123,
            'a': {
                'z': 123,
                'a': 532,
                'x': {
                    'a': 123,
                    'vvv': 54
                }
            }
        }

        sorted_dict = {
            'a': {
                'a': 532,
                'x': {
                 'a': 123,
                 'vvv': 54
                },
                'z': 123,
            },
            'z': 123
        }

        s = canonical.format_dictionary(unsorted)

        self.assertDictEqual(s, sorted_dict)

    def test_random_subblock_converts_successfully(self):
        sb = random_txs.random_block().subBlocks[0].to_dict()

        expected_order = ['inputHash', 'merkleLeaves', 'merkleRoot', 'signatures', 'subBlockNum', 'transactions']

        sorted_sb = canonical.format_dictionary(sb)
        sorted_sb_keys = list(sorted_sb.keys())
        for i in range(len(sorted_sb_keys)):
            self.assertEqual(sorted_sb_keys[i], expected_order[i])

    def test_random_subblocks_all_convert_successfully_at_top_level(self):
        expected_order = ['inputHash', 'merkleLeaves', 'merkleRoot', 'signatures', 'subBlockNum', 'transactions']

        block = random_txs.random_block()
        sbs = [block.subBlocks[i].to_dict() for i in range(len(block.subBlocks))]

        for sb in sbs:
            sorted_sb = canonical.format_dictionary(sb)
            sorted_sb_keys = list(sorted_sb.keys())
            for i in range(len(sorted_sb_keys)):
                self.assertEqual(sorted_sb_keys[i], expected_order[i])

    def test_random_subblock_all_transactiondata_convert_successfully(self):
        sb = random_txs.random_block().subBlocks[0].to_dict()

        sb = canonical.format_dictionary(sb)

        expected_order = ['stampsUsed', 'state', 'status', 'transaction']

        for tx in sb['transactions']:
            sorted_tx_keys = list(tx.keys())
            self.assertEqual(sorted_tx_keys, expected_order)

    def test_random_subblock_all_transactions_convert_successfully(self):
        sb = random_txs.random_block().subBlocks[0].to_dict()

        expected_order = ['contractName', 'functionName', 'kwargs', 'nonce', 'processor', 'sender', 'stampsSupplied']

        sb = canonical.format_dictionary(sb)

        for tx in sb['transactions']:
            sorted_tx_keys = list(tx['transaction']['payload'].keys())
            self.assertEqual(sorted_tx_keys, expected_order)

    def test_block_from_subblocks_verify_works(self):
        sbs = random_txs.random_block().subBlocks

        block = canonical.block_from_subblocks(subblocks=sbs, previous_hash=b'\x00' * 32, block_num=0)

        prev_hash = block['prevBlockHash']
        prop_hash = block['blockHash']

        valid = canonical.verify_block(sbs, prev_hash, prop_hash)

        self.assertTrue(valid)

