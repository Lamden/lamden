from unittest import TestCase
from lamden.crypto import canonical

genesis_block = {
    'hlc_timestamp': '0000-00-00T00:00:00.000000000Z_0',
    'number': 0,
    'previous': '0' * 64
}

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

    def test_block_hash_from_block(self):

        hash = canonical.block_hash_from_block(
            block_number=genesis_block.get('number'),
            previous_block_hash=genesis_block.get('previous'),
            hlc_timestamp=genesis_block.get('hlc_timestamp')
        )
        expected_hash = '2bb4e112aca11805538842bd993470f18f337797ec3f2f6ab02c47385caf088e'
        self.assertEqual(expected_hash, hash)

