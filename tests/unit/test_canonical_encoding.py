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

    def test_members_list_hash(self):
        members = ['a', 'b', 'c']

        hash = canonical.hash_members_list(
            members=members
        )

        expected_hash = '3a985da74fe225b2045c172d6bd390bd855f086e3e9d525b46bfe24511431532'
        self.assertEqual(expected_hash, hash)

    def test_create_proof_message_from_tx_results(self):
        tx_result =  {
            'hash': 'abd',
            'result': None,
            'stamps_used': 0,
            'state': {},
            'status': 0,
            'transaction': {}
        }

        proof_details = canonical.create_proof_message_from_tx_results(
            tx_result=tx_result,
            hlc_timestamp='0000-00-00T00:00:00.000000000Z_0',
            rewards=[],
            members=['a', 'b', 'c']
        )

        message = proof_details.get('message')
        members_list_hash = proof_details.get('members_list_hash')
        num_of_members = proof_details.get('num_of_members')

        self.assertIsNotNone(message)
        self.assertIsNotNone(members_list_hash)
        self.assertIsNotNone(num_of_members)

        self.assertEqual('bd0eedfa8ce62a77581712767c1a24ca1b2237dcd26218e640cf7235e6cd89f13a985da74fe225b2045c172d6bd390bd855f086e3e9d525b46bfe245114315323', proof_details.get('message'))
        self.assertEqual('3a985da74fe225b2045c172d6bd390bd855f086e3e9d525b46bfe24511431532', members_list_hash)
        self.assertEqual(3, num_of_members)

    def test_create_proof_message_from_proof(self):
        tx_result_hash = '74544f9231f9509f52fbb142b8f604b4ad92e7d143de1fd48d36ab01ec16ed2c'

        proof = {
          'signature': '9e28f6a2feaff9162a57699a8773a311320e8debb564853b3c0fb4a14073a27501c81da2bd5fff8232e497214fb176dabb6ecbecab37395ba22285c58df69a0e',
          'signer': 'fb53dc54f4bdb2a2b9ddf02b4d90490f6657325bc85be099d364b001ca3f17e1',
          'members_list_hash': '7f95d27127def4441fc5db902f4f8dffd7380f103541529cce866f332d355668',
          'num_of_members': 4
        }

        message = canonical.create_proof_message_from_proof(
            tx_result_hash=tx_result_hash,
            proof=proof
        )

        self.assertIsNotNone(message)

        self.assertEqual('74544f9231f9509f52fbb142b8f604b4ad92e7d143de1fd48d36ab01ec16ed2c7f95d27127def4441fc5db902f4f8dffd7380f103541529cce866f332d3556684', message)

