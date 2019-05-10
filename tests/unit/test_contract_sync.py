from unittest import TestCase
from cilantro_ee.contracts import sync


class TestContractSync(TestCase):
    def test_directory_to_filename_works(self):
        directory = '~/something/something/hello/this/is/a/path.txt'
        name = 'path'
        _name = sync.contract_name_from_file_path(directory)

        self.assertEqual(name, _name)

    def test_directory_to_filename_if_just_filename(self):
        directory = 'path.txt'
        name = 'path'
        _name = sync.contract_name_from_file_path(directory)

        self.assertEqual(name, _name)

    def test_directory_to_filename_if_many_extensions(self):
        directory = 'path.txt.a.s.g.we.2.d.g.a.s.c.g'
        name = 'path'
        _name = sync.contract_name_from_file_path(directory)

        self.assertEqual(name, _name)

