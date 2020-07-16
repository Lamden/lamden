from unittest import TestCase
from lamden.crypto import canonical


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
