from unittest import TestCase
from cilantro_ee.contracts import sync

class TestContract_sync(TestCase):
    def test_directory_to_filename_works(self):
        directory = '~/something/something/hello/this/is/a/path.txt'

        name = 'path'

        _name = sync.contract_name_from_file_path(directory)

        self.assertEqual(name, _name)