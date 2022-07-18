from unittest import TestCase

from lamden.crypto import block_validator
from lamden.crypto.wallet import Wallet
from lamden.crypto.block_validator import BLOCK_EXCEPTIONS, PROCESSED_TX_EXCEPTIONS, PAYLOAD_EXCEPTIONS
from lamden.crypto.canonical import format_dictionary
from copy import deepcopy

TRANSACTION = dict({
        "metadata": {
            "signature": "81d34f903f80a39969faf93174c384b1c9929a62b99ba5c33f77f66382a779e8e6e4ebdac5b8e4025a662b4669ec5e253b9c1521adad778209b2000cd5b54701"
        },
        "payload": {
            "contract": "currency",
            "function": "transfer",
            "kwargs": {
                "amount": {"__fixed__": "10.5"},
                "to": "12331ea5bfb49aca46004d5da40fb2b05ef26d0b4188787b230c330e2c4d018a"
            },
            "nonce": 1,
            "processor": "2462a8c76f145068ef9b6c926889772d82fcae19004abbbabab1fee2d2a1c5e1",
            "sender": "203c3e9807590023cb59c47e619e4f8e1d594d39f421789239b3bac424b2f506",
            "stamps_supplied": 20
        }
    })

PROCESSED_TRANSACTION = dict({
    "hash": "f05519affba9bec4c8e1e44d252cb2ade9353eb32294d0c4f238755e162ac4d4",
    "result": "None",
    "stamps_used": 1,
    "state": [
        {
            "key": "currency.balances:203c3e9807590023cb59c47e619e4f8e1d594d39f421789239b3bac424b2f506",
            "value": {"__fixed__": "999979.0"}
        },
        {
            "key": "currency.balances:12331ea5bfb49aca46004d5da40fb2b05ef26d0b4188787b230c330e2c4d018a",
            "value": {"__fixed__": "10.5"}
        }
    ],
    "status": 0,
    "transaction": TRANSACTION
})

BLOCK_V2 = dict({
    "hash": "6ee9a1f2b0c5d3d720814f8878cdaf36f2ceaaacad6619957390712b5237da70",
    "number": 2,
    "hlc_timestamp": "2022-07-06T18:15:00.379629056Z_0",
    "previous": "33c5777cc0880a501babee6ab9fbaf23ead7aa2e2b69a2c06e450bf66c9dd56e",
    "proofs": [
        {
            "signature": "c4b6dbd7a2786159849cd951a1b7e46f3b44653b713f2d4bddda449cab5f6cd59d1430c30df40146796aaa3d46ff1eabce52d9784a7c8e1daef4e6616aaa6d03",
            "signer": "0b13fae291610526d84497c5fe6d7e93696ea6927abbcfa6d85fd7b8aca04554"
        },
        {
            "signature": "4777b74c4cdcadd5df2ff292907547ff4ebac53c0865af033921c4cd5ffb9013201905a258e47a58d6f3e079afeeac1f2b686888f8a5c19dafeee447d07e8e00",
            "signer": "4a6290aa7c0b5964262d39df5a82ee23d8a730832a4c1ed0693e13502b439ac2"
        },
        {
            "signature": "dc339b1bcfc93574d38ae413de7537de388c38c90b2d2f81ed874f560880bf5148ae1d937c6f1b7e7a1a54bdfd416f7ca484a00ce4f17c6e5f47b9bda6b67506",
            "signer": "67b4d37b24025dc401b2f174b8435ff93090f16dbee3f67e24b64f2e555d865a"
        },
        {
            "signature": "be67d0eb51ee5ca10e8e3cb215a9cb95d9c8fbde90bfda787a474d643bdb01c909dbd8976bea767a9b22ee2b7074dce08eb3bf82e7b26b9ddca2f08a108f3903",
            "signer": "55296200c42ade25f6b7d32f2d7a6ed3e04b7a3a7c1d7cb65bb54dd607761aab"
        },
        {
            "signature": "de79bba578733ad85bbb4f79d9dea5409c61afea41b7d307f33cccc6a2c4ed2ca004e02ed6bcc6b1469f04c83d738a85ca5dc7ad2da1bb6c921445244a430101",
            "signer": "223b23ffb180ebd68f9fcddd804331b1dd2d53b86e2bf90eca54b4c5dcb6c571"
        },
        {
            "signature": "be616cc509b92a0a9d4846367c9b335951b6030c640cc9e1f53b02120b0b4944a6444f111b76cbdc71fd2a8a55edefe20bdcb6a74fbf58057d117f9f551ec40c",
            "signer": "ec5add0d16d4146016c3c868db8f39c6ce9bbc7ea42b4d2d46a3614d9616a5b0"
        }
    ],
    "processed": PROCESSED_TRANSACTION,
    "rewards": [
        {
            "key": "currency.balances:2462a8c76f145068ef9b6c926889772d82fcae19004abbbabab1fee2d2a1c5e1",
            "value": {"__fixed__": "0.00880000"},
            "reward": {"__fixed__": "0.00440000"}
        },
        {
            "key": "currency.balances:ec5add0d16d4146016c3c868db8f39c6ce9bbc7ea42b4d2d46a3614d9616a5b0",
            "value": {"__fixed__": "0.00880000"},
            "reward": {"__fixed__": "0.00440000"}
        },
        {
            "key": "currency.balances:09e5f8f3e697fb6ec55c3058bbd154d9bc581aca7f273907c207b64f3d9ca5f9",
            "value": {"__fixed__": "0.00880000"},
            "reward": {"__fixed__": "0.00440000"}
        },
        {
            "key": "currency.balances:4df9640eafaf9df7fa5da0fd33162860870c385990313adf4901b13daa1c3915",
            "value": {"__fixed__": "0.00880000"},
            "reward": {"__fixed__": "0.00440000"}
        },
        {
            "key": "currency.balances:0b13fae291610526d84497c5fe6d7e93696ea6927abbcfa6d85fd7b8aca04554",
            "value": {"__fixed__": "0.00880000"},
            "reward": {"__fixed__": "0.00440000"}
        },
        {
            "key": "currency.balances:4a6290aa7c0b5964262d39df5a82ee23d8a730832a4c1ed0693e13502b439ac2",
            "value": {"__fixed__": "0.00880000"},
            "reward": {"__fixed__": "0.00440000"}
        },
        {
            "key": "currency.balances:55296200c42ade25f6b7d32f2d7a6ed3e04b7a3a7c1d7cb65bb54dd607761aab",
            "value": {"__fixed__": "0.00880000"},
            "reward": {"__fixed__": "0.00440000"}
        },
        {
            "key": "currency.balances:223b23ffb180ebd68f9fcddd804331b1dd2d53b86e2bf90eca54b4c5dcb6c571",
            "value": {"__fixed__": "0.00880000"},
            "reward": {"__fixed__": "0.00440000"}
        },
        {
            "key": "currency.balances:eea02a5b3b7757ad10854699bacfa5ae31e834c56bf7a744f7fe8702a11ea458",
            "value": {"__fixed__": "0.00880000"},
            "reward": {"__fixed__": "0.00440000"}
        },
        {
            "key": "currency.balances:67b4d37b24025dc401b2f174b8435ff93090f16dbee3f67e24b64f2e555d865a",
            "value": {"__fixed__": "0.00880000"},
            "reward": {"__fixed__": "0.00440000"}
        },
        {
            "key": "currency.balances:0000803efd5df09c75c0c6670742db5074e5a011b829dfd8a0c50726d263a345",
            "value": {"__fixed__": "288090567.00100000"},
            "reward": {"__fixed__": "0.00050000"}
        },
        {
            "key": "currency.balances:sys",
            "value": {"__fixed__": "0.01000000"},
            "reward": {"__fixed__": "0.00500000"}
        }
    ],
    "origin": {
        "signature": "7cdd808568e55268ab5bf024cdb1bf1081ab300122c7cee0f7a0a1c4759a1898f9f89137c4c95d61507b0c62de7ad52eb6b1806b9c2a00070ee93f353fde3609",
        "sender": "2462a8c76f145068ef9b6c926889772d82fcae19004abbbabab1fee2d2a1c5e1"
    }
})

class TestBlockValidator(TestCase):
    def setUp(self):
        self.block = deepcopy(BLOCK_V2)
        self.wallet = Wallet()

    def test_verify_block__returns_TRUE_if_block_is_valid(self):
        self.assertTrue(block_validator.verify_block(
            block=self.block
        ))

    def test_verify_block__returns_FALSE_if_exception_is_raised(self):
        del self.block['hash']
        self.assertFalse(block_validator.verify_block(
            block=self.block
        ))

    def test_hash_is_sha256__retuns_TRUE_if_hash_is_valid(self):
        self.assertTrue(block_validator.hash_is_sha256(
            hash_str="a9d0cbe69b7217c85bbf685c94ed00e0eb0960ae7742cf789422f92da6ba1c86"
        ))

    def test_hash_is_sha256__retuns_False_if_hash_is_not_base_16(self):
        self.assertFalse(block_validator.hash_is_sha256(hash_str="a2f123123asd1"))

    def test_hash_is_sha256__retuns_False_if_hash_is_not_len_64(self):
        self.assertFalse(block_validator.hash_is_sha256(hash_str="a9d0cb"))

    def test_hash_is_sha256__retuns_False_if_hash_is_not_str(self):
        self.assertFalse(block_validator.hash_is_sha256(hash_str=1234))

    def test_hash_is_sha256_signature__retuns_TRUE_if_hash_is_valid(self):
        self.assertTrue(block_validator.hash_is_sha256_signature(
            signature="7cdd808568e55268ab5bf024cdb1bf1081ab300122c7cee0f7a0a1c4759a1898f9f89137c4c95d61507b0c62de7ad52eb6b1806b9c2a00070ee93f353fde3609"
        ))

    def test_hash_is_sha256_signature__retuns_False_if_hash_is_not_base_16(self):
        self.assertFalse(block_validator.hash_is_sha256_signature(signature="a2f123123asd1"))

    def test_hash_is_sha256_signature__retuns_False_if_hash_is_not_len_128(self):
        self.assertFalse(block_validator.hash_is_sha256_signature(signature="a9d0cb"))

    def test_hash_is_sha256_signature__retuns_False_if_hash_is_not_str(self):
        self.assertFalse(block_validator.hash_is_sha256_signature(signature=1234))

    def test_is_hcl_timestamp__returns_True_if_hlc_is_valid(self):
        self.assertTrue(block_validator.is_hlc_timestamp("2022-07-06T18:15:00.379629056Z_0"))

    def test_is_hcl_timestamp__returns_False_if_hlc_is_not_valid(self):
        self.assertFalse(block_validator.is_hlc_timestamp("202207T18:15:00.379629056"))

    def test_validate_block_structure__raises_no_exceptions_if_block_is_valid(self):
        self.assertTrue(block_validator.validate_block_structure(block=self.block))

    def test_validate_block_structure__raises_BlockHashMalformed(self):
        with self.assertRaises(block_validator.BlockHashMalformed) as err:
            self.block['hash'] = "123"
            block_validator.validate_block_structure(block=self.block)

        self.assertEqual(BLOCK_EXCEPTIONS['BlockHashMalformed'], str(err.exception))

        with self.assertRaises(block_validator.BlockHashMalformed) as err:
            self.block['hash'] = 'a2f123123asd1'
            block_validator.validate_block_structure(block=self.block)

        self.assertEqual(BLOCK_EXCEPTIONS['BlockHashMalformed'], str(err.exception))

        with self.assertRaises(block_validator.BlockHashMalformed) as err:
            del self.block['hash']
            block_validator.validate_block_structure(block=self.block)

        self.assertEqual(BLOCK_EXCEPTIONS['BlockHashMalformed'], str(err.exception))

    def test_validate_block_structure__raises_BlockPreviousHashMalformed(self):
        with self.assertRaises(block_validator.BlockPreviousHashMalformed) as err:
            self.block['previous'] = "a2f123123asd1"
            block_validator.validate_block_structure(block=self.block)

        self.assertEqual(BLOCK_EXCEPTIONS['BlockPreviousHashMalformed'], str(err.exception))

        with self.assertRaises(block_validator.BlockPreviousHashMalformed) as err:
            self.block['previous'] = '123'
            block_validator.validate_block_structure(block=self.block)

        self.assertEqual(BLOCK_EXCEPTIONS['BlockPreviousHashMalformed'], str(err.exception))

        with self.assertRaises(block_validator.BlockPreviousHashMalformed) as err:
            del self.block['previous']
            block_validator.validate_block_structure(block=self.block)

        self.assertEqual(BLOCK_EXCEPTIONS['BlockPreviousHashMalformed'], str(err.exception))

    def test_validate_block_structure__raises_BlockNumberInvalid(self):
        with self.assertRaises(block_validator.BlockNumberInvalid) as err:
            self.block['number'] = -1
            block_validator.validate_block_structure(block=self.block)

        self.assertEqual(BLOCK_EXCEPTIONS['BlockNumberInvalid'], str(err.exception))

        with self.assertRaises(block_validator.BlockNumberInvalid) as err:
            self.block['number'] = "1"
            block_validator.validate_block_structure(block=self.block)

        self.assertEqual(BLOCK_EXCEPTIONS['BlockNumberInvalid'], str(err.exception))

    def test_validate_block_structure__raises_BlockHLCInvalid(self):
        with self.assertRaises(block_validator.BlockHLCInvalid) as err:
            self.block['hlc_timestamp'] = "123"
            block_validator.validate_block_structure(block=self.block)

        self.assertEqual(BLOCK_EXCEPTIONS['BlockHLCInvalid'], str(err.exception))

        with self.assertRaises(block_validator.BlockHLCInvalid) as err:
            self.block['hlc_timestamp'] = 12343
            block_validator.validate_block_structure(block=self.block)

        self.assertEqual(BLOCK_EXCEPTIONS['BlockHLCInvalid'], str(err.exception))

    def test_validate_block_structure__raises_BlockOriginInvalid(self):
        with self.assertRaises(block_validator.BlockOriginInvalid) as err:
            self.block['origin'] = "123"
            block_validator.validate_block_structure(block=self.block)

        self.assertEqual(BLOCK_EXCEPTIONS['BlockOriginInvalid'], str(err.exception))

        with self.assertRaises(block_validator.BlockOriginInvalid) as err:
            del self.block['origin']
            block_validator.validate_block_structure(block=self.block)

        self.assertEqual(BLOCK_EXCEPTIONS['BlockOriginInvalid'], str(err.exception))

    def test_validate_block_structure__raises_BlockOriginSenderMalformed(self):
        with self.assertRaises(block_validator.BlockOriginSenderMalformed) as err:
            self.block['origin']['sender'] = "123"
            block_validator.validate_block_structure(block=self.block)

        self.assertEqual(BLOCK_EXCEPTIONS['BlockOriginSenderMalformed'], str(err.exception))

        with self.assertRaises(block_validator.BlockOriginSenderMalformed) as err:
            self.block['origin']['sender'] = "a2f123123asd1"
            block_validator.validate_block_structure(block=self.block)

        self.assertEqual(BLOCK_EXCEPTIONS['BlockOriginSenderMalformed'], str(err.exception))

        with self.assertRaises(block_validator.BlockOriginSenderMalformed) as err:
            del self.block['origin']['sender']
            block_validator.validate_block_structure(block=self.block)

        self.assertEqual(BLOCK_EXCEPTIONS['BlockOriginSenderMalformed'], str(err.exception))

    def test_validate_block_structure__raises_BlockOriginSignatureMalformed(self):
        with self.assertRaises(block_validator.BlockOriginSignatureMalformed) as err:
            self.block['origin']['signature'] = "123"
            block_validator.validate_block_structure(block=self.block)

        self.assertEqual(BLOCK_EXCEPTIONS['BlockOriginSignatureMalformed'], str(err.exception))

        with self.assertRaises(block_validator.BlockOriginSignatureMalformed) as err:
            self.block['origin']['signature'] = "a2f123123asd1"
            block_validator.validate_block_structure(block=self.block)

        self.assertEqual(BLOCK_EXCEPTIONS['BlockOriginSignatureMalformed'], str(err.exception))

        with self.assertRaises(block_validator.BlockOriginSignatureMalformed) as err:
            del self.block['origin']['signature']
            block_validator.validate_block_structure(block=self.block)

        self.assertEqual(BLOCK_EXCEPTIONS['BlockOriginSignatureMalformed'], str(err.exception))

    def test_validate_block_structure__raises_BlockRewardsInvalid(self):
        # Rewards can be an empty list
        self.block['rewards'] = []
        self.assertTrue(block_validator.validate_block_structure(block=self.block))

        with self.assertRaises(block_validator.BlockRewardsInvalid) as err:
            self.block['rewards'] = "123"
            block_validator.validate_block_structure(block=self.block)

        self.assertEqual(BLOCK_EXCEPTIONS['BlockRewardsInvalid'], str(err.exception))

        with self.assertRaises(block_validator.BlockRewardsInvalid) as err:
            del self.block['rewards']
            block_validator.validate_block_structure(block=self.block)

        self.assertEqual(BLOCK_EXCEPTIONS['BlockRewardsInvalid'], str(err.exception))

    def test_validate_block_structure__raises_BlockProofsInvalid(self):
        with self.assertRaises(block_validator.BlockProofsInvalid) as err:
            self.block['proofs'] = []
            block_validator.validate_block_structure(block=self.block)

        self.assertEqual(BLOCK_EXCEPTIONS['BlockProofsInvalid'], str(err.exception))

        with self.assertRaises(block_validator.BlockProofsInvalid) as err:
            self.block['proofs'] = "123"
            block_validator.validate_block_structure(block=self.block)

        self.assertEqual(BLOCK_EXCEPTIONS['BlockProofsInvalid'], str(err.exception))

        with self.assertRaises(block_validator.BlockProofsInvalid) as err:
            del self.block['proofs']
            block_validator.validate_block_structure(block=self.block)

        self.assertEqual(BLOCK_EXCEPTIONS['BlockProofsInvalid'], str(err.exception))

    def test_validate_block_structure__raises_BlockProcessedInvalid(self):
        with self.assertRaises(block_validator.BlockProcessedInvalid) as err:
            self.block['processed'] = "123"
            block_validator.validate_block_structure(block=self.block)

        self.assertEqual(BLOCK_EXCEPTIONS['BlockProcessedInvalid'], str(err.exception))

        with self.assertRaises(block_validator.BlockProcessedInvalid) as err:
            del self.block['processed']
            block_validator.validate_block_structure(block=self.block)

        self.assertEqual(BLOCK_EXCEPTIONS['BlockProcessedInvalid'], str(err.exception))

    def test_validate_all_hashes__returns_true_if_all_valid(self):
        self.assertTrue(block_validator.validate_all_hashes(block=self.block))

    def test_validate_all_hashes__raises_BlockHashMalformed(self):
        with self.assertRaises(block_validator.BlockHashMalformed) as err:
            self.block['hash'] = "123"
            block_validator.validate_all_hashes(block=self.block)
        self.assertEqual(BLOCK_EXCEPTIONS['BlockHashMalformed'], str(err.exception))

    def test_validate_all_hashes__raises_ProcessedTxHashMalformed(self):
        with self.assertRaises(block_validator.ProcessedTxHashMalformed) as err:
            self.block['processed']['hash'] = "123"
            block_validator.validate_all_hashes(block=self.block)
        self.assertEqual(PROCESSED_TX_EXCEPTIONS['ProcessedTxHashMalformed'], str(err.exception))

    def test_verify_transaction_signature__returns_True_if_signature_valid(self):
        tx = {
            "metadata": {
                "signature": 'bfa776bef57f5889622aac24b782febd009ed8949d0878a468f8458051b9bb61216cc64111096281f9fa8893e4e46644365151f121f14b95d54e17cc8e38050f'
            },
            "payload": {
                "contract": 'currency',
                "function": 'transfer',
                "kwargs": {
                    "amount": {"__fixed__": '500000'},
                    "to": '160c15c964f2cc51a6f5c1a1ffb1b6406ff2777ab45561da51e8cbd90bec2843'
                },
                "nonce": 0,
                "processor": '92e45fb91c8f76fbfdc1ff2a58c2e901f3f56ec38d2f10f94ac52fcfa56fce2e',
                "sender": '45f943fb2a63ac12ef9321af33322e514a873589400247ad983d278fa8b450b1',
                "stamps_supplied": 100
            }
        }

        tx_2 = {
            "metadata": {
                "signature": '81d34f903f80a39969faf93174c384b1c9929a62b99ba5c33f77f66382a779e8e6e4ebdac5b8e4025a662b4669ec5e253b9c1521adad778209b2000cd5b54701'
            },
            "payload": {
                "contract": 'currency',
                "function": 'transfer',
                "kwargs": {
                    "amount": {"__fixed__": "10.5"},
                    "to": '12331ea5bfb49aca46004d5da40fb2b05ef26d0b4188787b230c330e2c4d018a'
                },
                "nonce": 1,
                "processor": '2462a8c76f145068ef9b6c926889772d82fcae19004abbbabab1fee2d2a1c5e1',
                "sender": '203c3e9807590023cb59c47e619e4f8e1d594d39f421789239b3bac424b2f506',
                "stamps_supplied": 20
            }
        }
        self.assertTrue(block_validator.verify_transaction_signature(transaction=tx))
        #self.assertTrue(block_validator.verify_transaction_signature(transaction=tx_2))

    def test_verify_transaction_signature__testing(self):
        signature = "5e5cbcc7d3331e1f2d983c280fd88fc3bf4ee6582f9a253f4690b75920ce2c02b2d5704b30669d164523dbe2a3153ebd0ec7e12332a3f8f2028590547bcf600c"
        payload = {"contract": "con_testing", "function": "test_values", "kwargs": {"Str": "test string", "UID": "lamdenjs-testing"}, "nonce": 0, "processor": "3d11988757d79e72725bad8998c9437e06228b1eef84d1282f1721187530da06", "sender": "bf06942178b2203b36abec66593a0b84bd9629a33b7c970874cc5850dd62f369", "stamps_supplied": 100}

        self.assertTrue(block_validator.verify_transaction_signature(transaction={
            "metadata": {"signature": signature},
            "payload": payload
        }))

    def test_verify_origin_signature__returns_True_if_signature_valid(self):
        self.assertTrue(block_validator.verify_origin_signature(block=self.block))

    def test_verify_proof__returns_True_if_signature_valid(self):
        tx_result = self.block.get('processed')
        rewards = self.block.get('rewards')
        hlc_timestamp = self.block.get('hlc_timestamp')

        proofs = self.block.get('proofs')
        self.assertTrue(block_validator.verify_proof(
            proof=proofs[0],
            tx_result=tx_result,
            rewards=rewards,
            hlc_timestamp=hlc_timestamp
        ))

    def test_verify_proofs__returns_True_if_all_signatures_are_valid(self):
        self.assertTrue(block_validator.verify_proofs(block=self.block))

    def test_validate_all_signatures__returns_true_if_all_valid(self):
        self.assertTrue(block_validator.validate_all_signatures(block=self.block))

    def test_validate_all_signatures__raises_TransactionMetadataSignatureMalformed(self):
        with self.assertRaises(block_validator.ProcessedTxHashMalformed) as err:
            self.block['processed']['transaction']['payload']['contract'] = "123"
            block_validator.validate_all_signatures(block=self.block)
        self.assertEqual(PROCESSED_TX_EXCEPTIONS['ProcessedTxHashMalformed'], str(err.exception))

    def test_validate_all_signatures__raises_BlockOriginSignatureMalformed(self):
        with self.assertRaises(block_validator.BlockOriginSignatureMalformed) as err:
            self.block['processed']['transaction']['payload']['contract'] = "123"
            block_validator.validate_all_signatures(block=self.block)
        self.assertEqual(BLOCK_EXCEPTIONS['BlockOriginSignatureMalformed'], str(err.exception))

    def test_validate_all_signatures__raises_BlockProofMalformed(self):
        bad_proof = {
            'signer': self.wallet.verifying_key,
            'signature': self.wallet.sign(f'TESTING')
        }

        with self.assertRaises(block_validator.BlockProofMalformed) as err:
            self.block['proofs'].append(bad_proof)
            block_validator.validate_all_signatures(block=self.block)
        self.assertEqual(BLOCK_EXCEPTIONS['BlockProofMalformed'], str(err.exception))

'''
PROCESSED_TRANSACTION = {
    "hash": "f05519affba9bec4c8e1e44d252cb2ade9353eb32294d0c4f238755e162ac4d4",
    "result": "None",
    "stamps_used": 1,
    "state": [
        {
            "key": "currency.balances:203c3e9807590023cb59c47e619e4f8e1d594d39f421789239b3bac424b2f506",
            "value": {"__fixed__": "999979.0"}
        },
        {
            "key": "currency.balances:12331ea5bfb49aca46004d5da40fb2b05ef26d0b4188787b230c330e2c4d018a",
            "value": {"__fixed__": "10.5"}
        }
    ],
    "status": 0,e
    "transaction": {
        "metadata": {
            "signature": "81d34f903f80a39969faf93174c384b1c9929a62b99ba5c33f77f66382a779e8e6e4ebdac5b8e4025a662b4669ec5e253b9c1521adad778209b2000cd5b54701"
        },
        "payload": {
            "contract": "currency",
            "function": "transfer",
            "kwargs": {
                "amount": {"__fixed__": "10.5"},
                "to": "12331ea5bfb49aca46004d5da40fb2b05ef26d0b4188787b230c330e2c4d018a"
            },
            "nonce": 1,
            "processor": "2462a8c76f145068ef9b6c926889772d82fcae19004abbbabab1fee2d2a1c5e1",
            "sender": "203c3e9807590023cb59c47e619e4f8e1d594d39f421789239b3bac424b2f506",
            "stamps_supplied": 20
        }
    }
},
'''


class TestProcessedTransactionValidator(TestCase):
    def setUp(self):
        self.processed = deepcopy(PROCESSED_TRANSACTION)

    def test_validate_processed_transaction_structure__returns_TRUE_if_valid(self):
        self.assertTrue(block_validator.validate_processed_transaction_structure(self.processed))

    def test_validate_processed_transaction_structure__raises_ProcessedTxHashMalformed(self):
        with self.assertRaises(block_validator.ProcessedTxHashMalformed) as err:
            self.processed['hash'] = '123'
            block_validator.validate_processed_transaction_structure(processed_transaction=self.processed)

        self.assertEqual(PROCESSED_TX_EXCEPTIONS['ProcessedTxHashMalformed'], str(err.exception))

        with self.assertRaises(block_validator.ProcessedTxHashMalformed) as err:
            self.processed['hash'] = 'a2f123123asd1'
            block_validator.validate_processed_transaction_structure(processed_transaction=self.processed)

        self.assertEqual(PROCESSED_TX_EXCEPTIONS['ProcessedTxHashMalformed'], str(err.exception))

        with self.assertRaises(block_validator.ProcessedTxHashMalformed) as err:
            del self.processed['hash']
            block_validator.validate_processed_transaction_structure(processed_transaction=self.processed)

        self.assertEqual(PROCESSED_TX_EXCEPTIONS['ProcessedTxHashMalformed'], str(err.exception))

    def test_validate_processed_transaction_structure__raises_ProcessedTxResultInvalid(self):
        with self.assertRaises(block_validator.ProcessedTxResultInvalid) as err:
            self.processed['result'] = 123
            block_validator.validate_processed_transaction_structure(processed_transaction=self.processed)

        self.assertEqual(PROCESSED_TX_EXCEPTIONS['ProcessedTxResultInvalid'], str(err.exception))

        with self.assertRaises(block_validator.ProcessedTxResultInvalid) as err:
            del self.processed['result']
            block_validator.validate_processed_transaction_structure(processed_transaction=self.processed)

        self.assertEqual(PROCESSED_TX_EXCEPTIONS['ProcessedTxResultInvalid'], str(err.exception))

    def test_validate_processed_transaction_structure__raises_ProcessedTxStampsUsedInvalid(self):
        with self.assertRaises(block_validator.ProcessedTxStampsUsedInvalid) as err:
            self.processed['stamps_used'] = -123
            block_validator.validate_processed_transaction_structure(processed_transaction=self.processed)

        self.assertEqual(PROCESSED_TX_EXCEPTIONS['ProcessedTxStampsUsedInvalid'], str(err.exception))

        with self.assertRaises(block_validator.ProcessedTxStampsUsedInvalid) as err:
            del self.processed['stamps_used']
            block_validator.validate_processed_transaction_structure(processed_transaction=self.processed)

        self.assertEqual(PROCESSED_TX_EXCEPTIONS['ProcessedTxStampsUsedInvalid'], str(err.exception))
        
    def test_validate_processed_transaction_structure__raises_ProcessedTxStateInvalid(self):
        ## Emppty State change list will pass
        self.processed['state'] = []
        self.assertTrue(block_validator.validate_processed_transaction_structure(processed_transaction=self.processed))
        
        with self.assertRaises(block_validator.ProcessedTxStateInvalid) as err:
            del self.processed['state']
            block_validator.validate_processed_transaction_structure(processed_transaction=self.processed)

        self.assertEqual(PROCESSED_TX_EXCEPTIONS['ProcessedTxStateInvalid'], str(err.exception))

    def test_validate_processed_transaction_structure__raises_ProcessedTxStateEntryInvalid(self):
        with self.assertRaises(block_validator.ProcessedTxStateEntryInvalid) as err:
            self.processed['state'] = [
                {
                    "key": "currency.balances:203c3e9807590023cb59c47e619e4f8e1d594d39f421789239b3bac424b2f506"
                }
            ]
            block_validator.validate_processed_transaction_structure(processed_transaction=self.processed)
        self.assertEqual(PROCESSED_TX_EXCEPTIONS['ProcessedTxStateEntryInvalid'], str(err.exception))

        with self.assertRaises(block_validator.ProcessedTxStateEntryInvalid) as err:
            self.processed['state'] = [
                {
                    "value": "123"
                }
            ]
            block_validator.validate_processed_transaction_structure(processed_transaction=self.processed)
        self.assertEqual(PROCESSED_TX_EXCEPTIONS['ProcessedTxStateEntryInvalid'], str(err.exception))

        with self.assertRaises(block_validator.ProcessedTxStateEntryInvalid) as err:
            self.processed['state'] = [
                {
                    "key": 123,
                    "value": "abc"
                }
            ]
            block_validator.validate_processed_transaction_structure(processed_transaction=self.processed)
        self.assertEqual(PROCESSED_TX_EXCEPTIONS['ProcessedTxStateEntryInvalid'], str(err.exception))

    def test_validate_processed_transaction_structure__raises_ProcessedTxStatusInvalid(self):
        with self.assertRaises(block_validator.ProcessedTxStatusInvalid) as err:
            del self.processed['status']
            block_validator.validate_processed_transaction_structure(processed_transaction=self.processed)

        self.assertEqual(PROCESSED_TX_EXCEPTIONS['ProcessedTxStatusInvalid'], str(err.exception))

    def test_validate_processed_transaction_structure__raises_ProcessedTransactionPayloadInvalid(self):
        with self.assertRaises(block_validator.ProcessedTransactionPayloadInvalid) as err:
            del self.processed['transaction']
            block_validator.validate_processed_transaction_structure(processed_transaction=self.processed)

        self.assertEqual(PROCESSED_TX_EXCEPTIONS['ProcessedTransactionPayloadInvalid'], str(err.exception))

'''
PAYLOAD = dict({
        "metadata": {
            "signature": "81d34f903f80a39969faf93174c384b1c9929a62b99ba5c33f77f66382a779e8e6e4ebdac5b8e4025a662b4669ec5e253b9c1521adad778209b2000cd5b54701"
        },
        "payload": {
            "contract": "currency",
            "function": "transfer",
            "kwargs": {
                "amount": {"__fixed__": "10.5"},
                "to": "12331ea5bfb49aca46004d5da40fb2b05ef26d0b4188787b230c330e2c4d018a"
            },
            "nonce": 1,
            "processor": "2462a8c76f145068ef9b6c926889772d82fcae19004abbbabab1fee2d2a1c5e1",
            "sender": "203c3e9807590023cb59c47e619e4f8e1d594d39f421789239b3bac424b2f506",
            "stamps_supplied": 20
        }
    })
'''


class TestTransactionValidator(TestCase):
    def setUp(self):
        self.transaction = deepcopy(TRANSACTION)

    def test_validate_transaction_structure__returns_TRUE_if_payload_is_valid(self):
        self.assertTrue(block_validator.validate_transaction_structure(transaction=self.transaction))

    def test_validate_transaction_structure__raises_TransactionMetadataInvalid(self):
        with self.assertRaises(block_validator.TransactionMetadataInvalid) as err:
            del self.transaction['metadata']
            block_validator.validate_transaction_structure(transaction=self.transaction)

        self.assertEqual(PAYLOAD_EXCEPTIONS['TransactionMetadataInvalid'], str(err.exception))

    def test_validate_transaction_structure__raises_TransactionMetadataSignatureMalformed(self):
        with self.assertRaises(block_validator.TransactionMetadataSignatureMalformed) as err:
            self.transaction['metadata']['signature'] = '123'
            block_validator.validate_transaction_structure(transaction=self.transaction)
        self.assertEqual(PAYLOAD_EXCEPTIONS['TransactionMetadataSignatureMalformed'], str(err.exception))

        with self.assertRaises(block_validator.TransactionMetadataSignatureMalformed) as err:
            self.transaction['metadata']['signature'] = 'a2f123123asd1'
            block_validator.validate_transaction_structure(transaction=self.transaction)
        self.assertEqual(PAYLOAD_EXCEPTIONS['TransactionMetadataSignatureMalformed'], str(err.exception))

        with self.assertRaises(block_validator.TransactionMetadataSignatureMalformed) as err:
            del self.transaction['metadata']['signature']
            block_validator.validate_transaction_structure(transaction=self.transaction)
        self.assertEqual(PAYLOAD_EXCEPTIONS['TransactionMetadataSignatureMalformed'], str(err.exception))

    def test_validate_transaction_structure__raises_TransactionPayloadInvalid(self):
        with self.assertRaises(block_validator.TransactionPayloadInvalid) as err:
            del self.transaction['payload']
            block_validator.validate_transaction_structure(transaction=self.transaction)

        self.assertEqual(PAYLOAD_EXCEPTIONS['TransactionPayloadInvalid'], str(err.exception))

    def test_validate_transaction_structure__raises_TransactionPayloadContractInvalid(self):
        with self.assertRaises(block_validator.TransactionPayloadContractInvalid) as err:
            del self.transaction['payload']['contract']
            block_validator.validate_transaction_structure(transaction=self.transaction)

        self.assertEqual(PAYLOAD_EXCEPTIONS['TransactionPayloadContractInvalid'], str(err.exception))

    def test_validate_transaction_structure__raises_TransactionPayloadFunctionInvalid(self):
        with self.assertRaises(block_validator.TransactionPayloadFunctionInvalid) as err:
            del self.transaction['payload']['function']
            block_validator.validate_transaction_structure(transaction=self.transaction)

        self.assertEqual(PAYLOAD_EXCEPTIONS['TransactionPayloadFunctionInvalid'], str(err.exception))

    def test_validate_transaction_structure__raises_TransactionPayloadKwargsInvalid(self):
        with self.assertRaises(block_validator.TransactionPayloadKwargsInvalid) as err:
            del self.transaction['payload']['kwargs']
            block_validator.validate_transaction_structure(transaction=self.transaction)

        self.assertEqual(PAYLOAD_EXCEPTIONS['TransactionPayloadKwargsInvalid'], str(err.exception))

    def test_validate_transaction_structure__raises_TransactionPayloadNonceInvalid(self):
        with self.assertRaises(block_validator.TransactionPayloadNonceInvalid) as err:
            self.transaction['payload']['nonce'] = -1
            block_validator.validate_transaction_structure(transaction=self.transaction)

        self.assertEqual(PAYLOAD_EXCEPTIONS['TransactionPayloadNonceInvalid'], str(err.exception))

        with self.assertRaises(block_validator.TransactionPayloadNonceInvalid) as err:
            del self.transaction['payload']['nonce']
            block_validator.validate_transaction_structure(transaction=self.transaction)

        self.assertEqual(PAYLOAD_EXCEPTIONS['TransactionPayloadNonceInvalid'], str(err.exception))

    def test_validate_transaction_structure__raises_TransactionPayloadProcessorMalformed(self):
        with self.assertRaises(block_validator.TransactionPayloadProcessorMalformed) as err:
            self.transaction['payload']['processor'] = '123'
            block_validator.validate_transaction_structure(transaction=self.transaction)
        self.assertEqual(PAYLOAD_EXCEPTIONS['TransactionPayloadProcessorMalformed'], str(err.exception))

        with self.assertRaises(block_validator.TransactionPayloadProcessorMalformed) as err:
            self.transaction['payload']['processor'] = 'a2f123123asd1'
            block_validator.validate_transaction_structure(transaction=self.transaction)
        self.assertEqual(PAYLOAD_EXCEPTIONS['TransactionPayloadProcessorMalformed'], str(err.exception))

        with self.assertRaises(block_validator.TransactionPayloadProcessorMalformed) as err:
            del self.transaction['payload']['processor']
            block_validator.validate_transaction_structure(transaction=self.transaction)
        self.assertEqual(PAYLOAD_EXCEPTIONS['TransactionPayloadProcessorMalformed'], str(err.exception))

    def test_validate_transaction_structure__raises_TransactionPayloadSenderMalformed(self):
        with self.assertRaises(block_validator.TransactionPayloadSenderMalformed) as err:
            self.transaction['payload']['sender'] = '123'
            block_validator.validate_transaction_structure(transaction=self.transaction)
        self.assertEqual(PAYLOAD_EXCEPTIONS['TransactionPayloadSenderMalformed'], str(err.exception))

        with self.assertRaises(block_validator.TransactionPayloadSenderMalformed) as err:
            self.transaction['payload']['sender'] = 'a2f123123asd1'
            block_validator.validate_transaction_structure(transaction=self.transaction)
        self.assertEqual(PAYLOAD_EXCEPTIONS['TransactionPayloadSenderMalformed'], str(err.exception))

        with self.assertRaises(block_validator.TransactionPayloadSenderMalformed) as err:
            del self.transaction['payload']['sender']
            block_validator.validate_transaction_structure(transaction=self.transaction)
        self.assertEqual(PAYLOAD_EXCEPTIONS['TransactionPayloadSenderMalformed'], str(err.exception))

    def test_validate_transaction_structure__raises_TransactionPayloadStampSuppliedInvalid(self):
        with self.assertRaises(block_validator.TransactionPayloadStampSuppliedInvalid) as err:
            self.transaction['payload']['stamps_supplied'] = -1
            block_validator.validate_transaction_structure(transaction=self.transaction)

        self.assertEqual(PAYLOAD_EXCEPTIONS['TransactionPayloadStampSuppliedInvalid'], str(err.exception))

        with self.assertRaises(block_validator.TransactionPayloadStampSuppliedInvalid) as err:
            del self.transaction['payload']['stamps_supplied']
            block_validator.validate_transaction_structure(transaction=self.transaction)

        self.assertEqual(PAYLOAD_EXCEPTIONS['TransactionPayloadStampSuppliedInvalid'], str(err.exception))
