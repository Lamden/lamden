from unittest import TestCase
from cilantro_ee.contracts import sync
from cilantro_ee.services.storage.vkbook import VKBook
from contracting.db.driver import ContractDriver
from contracting.client import ContractingClient


class TestContractSync(TestCase):
    def setup(self):
        masternodes = ['a', 'b', 'c']
        delegates = ['d', 'e', 'f']
        stamps = False
        nonces = False

        #v = VKBook(masternodes, delegates, stamps=stamps, nonces=nonces, debug=False)
        #self.assertIsNotNone(v)

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

    def test_sync_genesis_contracts_if_none_in_instance(self):
        driver = ContractDriver()
        driver.flush()

        sync.sync_genesis_contracts()

        submission = driver.get_contract('submission')
        currency = driver.get_contract('currency')
        upgrade = driver.get_contract('upgrade')

        self.assertIsNotNone(submission)
        self.assertIsNotNone(currency)
        self.assertIsNotNone(upgrade)

    def test_sync_genesis_contracts_if_one_deleted(self):
        driver = ContractDriver()
        driver.flush()

        sync.sync_genesis_contracts()

        driver.delete_contract('submission')

        sync.sync_genesis_contracts()

        submission = driver.get_contract('submission')
        currency = driver.get_contract('currency')
        upgrade = driver.get_contract('upgrade')

        self.assertIsNotNone(submission)
        self.assertIsNotNone(currency)
        self.assertIsNotNone(upgrade)

    def test_sync_genesis_contracts_if_none_deleted(self):
        driver = ContractDriver()
        driver.flush()

        sync.sync_genesis_contracts()
        sync.sync_genesis_contracts()

        submission = driver.get_contract('submission')
        currency = driver.get_contract('currency')
        upgrade = driver.get_contract('upgrade')

        self.assertIsNotNone(submission)
        self.assertIsNotNone(currency)
        self.assertIsNotNone(upgrade)

    def test_submit_contract_with_specific_construction_args(self):
        driver = ContractDriver()
        driver.flush()

        sync.submit_contract_with_construction_args('vkbook', args={
            'masternodes': ['stu', 'raghu'],
            'delegates': ['tejas', 'monica'],
            'num_boot_mns': 1,
            'num_boot_del': 1
        })

        client = ContractingClient()
        vkbook = client.get_contract('vkbook')

        self.assertEqual(vkbook.get_masternodes(), ['stu', 'raghu'])
        self.assertEqual(vkbook.get_delegates(), ['tejas', 'monica'])
