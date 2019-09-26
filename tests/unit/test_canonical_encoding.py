from unittest import TestCase
from cilantro_ee.core import canonical


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

    def test_bytes_get_turned_to_hex(self):
        a = b'123'.hex()

        b = {
            'b': b'123'
        }

        s = canonical.format_dictionary(b)

        self.assertEqual(s['b'], a)
