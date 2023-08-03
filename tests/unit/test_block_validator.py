from contracting.db.encoder import encode
from copy import deepcopy
from lamden.crypto import block_validator
from lamden.crypto.block_validator import BLOCK_EXCEPTIONS, PROCESSED_TX_EXCEPTIONS, PAYLOAD_EXCEPTIONS
from lamden.crypto.wallet import Wallet
from unittest import TestCase

TRANSACTION = dict({
      "metadata": {
        "signature": "e832a8bfd4ba9598bdf380547342a8f8cd431a77d1d1f080fbe665e43bfcd20a3a4c67e6aa4ed0fad2504b7b399fc04617b5597d4bae7350a0babf93e2439c07",
        "timestamp": 1658163894
      },
      "payload": {
        "contract": "currency",
        "function": "transfer",
        "kwargs": {
          "amount": {
            "__fixed__": "499900"
          },
          "to": "c0006724aa6fc81619b7e27816e69ab824ad04d39640bb87fb86720f452a1ed5"
        },
        "nonce": 0,
        "processor": "92e45fb91c8f76fbfdc1ff2a58c2e901f3f56ec38d2f10f94ac52fcfa56fce2e",
        "sender": "3515aa7b15d7b97855a0266935bf26c44ad8d8198b2dc81ce035ba1b86b0f340",
        "stamps_supplied": 100
      }
    })

PROCESSED_TRANSACTION = dict({
    "hash": "bedbf2872cf337c40408d3b17f1ed649af173e812156d7066ccabc8cda26ad4a",
    "result": "None",
    "stamps_used": 1,
    "state": [
      {
        "key": "currency.balances:3515aa7b15d7b97855a0266935bf26c44ad8d8198b2dc81ce035ba1b86b0f340",
        "value": {
          "__fixed__": "50"
        }
      },
      {
        "key": "currency.balances:c0006724aa6fc81619b7e27816e69ab824ad04d39640bb87fb86720f452a1ed5",
        "value": {
          "__fixed__": "499900"
        }
      }
    ],
    "status": 0,
    "transaction": TRANSACTION
  })

BLOCK_V2 = dict({
  "hash": "accad90068e248f9c1df68095c491af389b18cde26402fd01cd602c5238663ce",
  "number": "1658163894967101696",
  "hlc_timestamp": "2022-07-18T17:04:54.967101696Z_0",
  "previous": "15707bfc75f0140a66dd1303fc5a9101006193e0278da880f2db483d3f21d646",
  "proofs": [
    {
      "signature": "32192497c0332b60f30ab7264a304dbd26a98851455b129c73f11ed9345c6eb78ea1673ed715706f1955fbd8a11c3e00e7506d1b2fa464481d2bca36a40c0701",
      "signer": "3cc7090dab1cc57df4d75be68d9f9cdbdbff639095488b68b0f90014f5cd20bc"
    },
    {
      "signature": "f1366e72f7c6179ba4bd6330fc11173e992b4ae77088a32d873edfa332faf90e8843f707eae5fc5735236780cc809cb442fdf1392bc097c7b26f5823fe84ec0d",
      "signer": "1c37fa8be2f0d029cd2c66d53fa2797c4697e127af556f123f662302cb0670c4"
    },
    {
      "signature": "eef303a975c3e28af5941d7746ca40e2a07b989603686ff0a2967a6ead04c7a2cc8392a9ed2023f0306e5c5001deea4ff757219fec8443a1d070ab7a3bd1810d",
      "signer": "a9d0cbe69b7217c85bbf685c94ed00e0eb0960ae7742cf789422f92da6ba1c86"
    },
    {
      "signature": "3ddf2a6b3026219bccd1a5e9970a814014626fd4643dc1883f8d058705cc3c82a94eb1752b9e882471a44d737178220e3e2b7321d7f5f74c6038be1fb4ebdc03",
      "signer": "41f48cd73574e6cbb5c5329eac7a5404eb12ee5a964d034044727fa3f4acbc9f"
    }
  ],
  "processed": PROCESSED_TRANSACTION,
  "rewards": [
    {
      "key": "currency.balances:92e45fb91c8f76fbfdc1ff2a58c2e901f3f56ec38d2f10f94ac52fcfa56fce2e",
      "value": {
        "__fixed__": "0.021999999"
      },
      "reward": {
        "__fixed__": "0.007333333"
      }
    },
    {
      "key": "currency.balances:01dcfdde08d22e837b0bdda38d2096cc23f05008c3253251ae70fe5477dd24b2",
      "value": {
        "__fixed__": "0.021999999"
      },
      "reward": {
        "__fixed__": "0.007333333"
      }
    },
    {
      "key": "currency.balances:a9d0cbe69b7217c85bbf685c94ed00e0eb0960ae7742cf789422f92da6ba1c86",
      "value": {
        "__fixed__": "0.021999999"
      },
      "reward": {
        "__fixed__": "0.007333333"
      }
    },
    {
      "key": "currency.balances:3cc7090dab1cc57df4d75be68d9f9cdbdbff639095488b68b0f90014f5cd20bc",
      "value": {
        "__fixed__": "0.021999999"
      },
      "reward": {
        "__fixed__": "0.007333333"
      }
    },
    {
      "key": "currency.balances:1c37fa8be2f0d029cd2c66d53fa2797c4697e127af556f123f662302cb0670c4",
      "value": {
        "__fixed__": "0.021999999"
      },
      "reward": {
        "__fixed__": "0.007333333"
      }
    },
    {
      "key": "currency.balances:41f48cd73574e6cbb5c5329eac7a5404eb12ee5a964d034044727fa3f4acbc9f",
      "value": {
        "__fixed__": "0.021999999"
      },
      "reward": {
        "__fixed__": "0.007333333"
      }
    },
    {
      "key": "currency.balances:45f943fb2a63ac12ef9321af33322e514a873589400247ad983d278fa8b450b1",
      "value": {
        "__fixed__": "287590567.00150000"
      },
      "reward": {
        "__fixed__": "0.00050000"
      }
    },
    {
      "key": "currency.balances:sys",
      "value": {
        "__fixed__": "0.01500000"
      },
      "reward": {
        "__fixed__": "0.00500000"
      }
    }
  ],
  "origin": {
    "signature": "024850ef8591bf0020ce10e53e305f0daf90ad026e3b9bcaf9524807208b24c3dfb3f54ab93f4db5c8d65fa3a29d3991a27330715ecfcf2b3c8a5989b5ea7508",
    "sender": "92e45fb91c8f76fbfdc1ff2a58c2e901f3f56ec38d2f10f94ac52fcfa56fce2e"
  }
})

BLOCK_V3 = {
  'hlc_timestamp': '2023-07-18T19:20:55.238093056Z_0',
  'number': '1689708055238093056',
  'previous': '9efb440eb91cd0c5c0fd35515da2f1e47ea9100b2ba3f117615bb9429c487552',
  'hash': '5f99c6e55236f67c55ffd254dfca020e0ce5b74b8310a571dd62dfef5c76abdf',
  'origin': {
    'sender': '36dd10028a604626bbbfee7cb53f1591e6af9afd05690d30b47368be4e1375b9',
    'signature': '4bf46a12b20b55e916a2851f090cf0833fe04ef95ac1a0c54ee745e777a5ce99da1c3a46120e19f61501f8be560b3077c1f60a8d7a59cdd92cd75f5e6e01dc08'
  },
  'rewards': [

  ],
  'processed': {
    'result': 'None',
    'stamps_used': 0,
    'state': [
      {
        'key': 'currency.balances:ff8e1bef1c59a15b23458a9ab727078f95455320bb8b99067a7072b6e486273a',
        'value': {
          '__fixed__': '10.5'
        }
      }
    ],
    'status': 0,
    'transaction': {
      'metadata': {
        'signature': 'f82041ace705d377d35888e23a84f3ef3bfa3719a30f7e07be8367c944b0049caf4c17976ddaea6a89ae2161f5722b996f42c260a539a464b6669f5195270e08'
      },
      'payload': {
        'contract': 'currency',
        'function': 'transfer',
        'kwargs': {
          'amount': {
            '__fixed__': '10.5'
          },
          'to': 'ff8e1bef1c59a15b23458a9ab727078f95455320bb8b99067a7072b6e486273a'
        },
        'nonce': 0,
        'processor': '36dd10028a604626bbbfee7cb53f1591e6af9afd05690d30b47368be4e1375b9',
        'sender': '6489a7ed5908d52bfa739bf02a3d77865f992555295cde011f7e7674aa6e368e',
        'stamps_supplied': 20
      }
    },
    'hash': '876111ec550a6be2794f4c57ea2a1cacc8ad00e556fb3ae7454955d536d344eb'
  },
  'proofs': [
    {
      'signature': 'b06ff32d674408e71ddd5738b33249bdd7c83e56b9ad17da5fb7b3488fb6819851b5da9e5fbbe7de0f99260577f61cfbb1d8d2915c8173f67c3dd4dd0b1ded01',
      'signer': '8a2ae298a08a36c6803d61f89cc63c0b1bf8875f86f54e9f655a8d5588e9beee',
      'members_list_hash': '65171446bbe235545db41b31c2d77cd6bf4bd5adc3bbe9f66a5f02ed6bc3d391',
      'num_of_members': 4
    },
    {
      'signature': '36976de0135785b8672a304f49f5adb3faab4a6b2e628eb4a5654362b5e4d0e0bfa189ebacb0d2fa41b629473264265d3e7342fae76eb2d7ad6784be4c257e0a',
      'signer': '684f78e0f2d15a84125b7d9a3880f1cffed6ffe910391db297f7dd8c62a44c01',
      'members_list_hash': '65171446bbe235545db41b31c2d77cd6bf4bd5adc3bbe9f66a5f02ed6bc3d391',
      'num_of_members': 4
    },
    {
      'signature': 'f5c9a219d65f6dc7869d0c9c8f3270d9ae9606ad7ca0279ac255600870e115bad4de2cdf4d3e5527277e41faf3b3cbfd880ecc5ff7c580bc11cd3b3be97a2705',
      'signer': '3dd5edc531118766fcb197ff8f09a959a5c22c33fc1d9d06630fed9139ce6089',
      'members_list_hash': '65171446bbe235545db41b31c2d77cd6bf4bd5adc3bbe9f66a5f02ed6bc3d391',
      'num_of_members': 4
    },
    {
      'signature': '0f4c9c3998e8b0fd6301f5f6a1df760d4e0f2ffbfa02c3e950bcbd2a03e4535d5a49a5cacd40e81c03df20ab3d9275efb1788e9c49402116f34e478990d9d700',
      'signer': 'abb3864825892ebb46c12990b5cf5de7f46e963f9f3c3e0e5f283460cbae8413',
      'members_list_hash': '65171446bbe235545db41b31c2d77cd6bf4bd5adc3bbe9f66a5f02ed6bc3d391',
      'num_of_members': 4
    }
  ],
  'minted': {
    'minter': 'abb3864825892ebb46c12990b5cf5de7f46e963f9f3c3e0e5f283460cbae8413',
    'signature': 'fd15459f936db3cece94175a9ae3ee0a0b1fa6c8ab82b770c59415b7e18f4d162908f94c73ddd31561e139b32a28c7d9ae2d9b3a10a2749fc271ece110d62e06'
  }
}

GENESIS_BLOCK = {
    'hash': '2bb4e112aca11805538842bd993470f18f337797ec3f2f6ab02c47385caf088e',
    'number': "0",
    'hlc_timestamp': '0000-00-00T00:00:00.000000000Z_0',
    'previous': '0000000000000000000000000000000000000000000000000000000000000000',
    'genesis': [
        {'key': 'currency.balances:9fb2b57b1740e8d86ecebe5bb1d059628df02236b69ed74de38b5e9d71230286', 'value': 100000000}
    ],
    'origin': {
        'sender': '9fb2b57b1740e8d86ecebe5bb1d059628df02236b69ed74de38b5e9d71230286',
        'signature': '82beb173f13ecc239ac108789b45428110ff56a84a3d999c0a1251a22974ea9b426ef61b13e04819d19556657448ba49a2f37230b8450b4de28a1a3cc85a3504'
    }
}

class TestBlockValidator(TestCase):
    def setUp(self):
        self.block = deepcopy(BLOCK_V2)
        self.block_v3 = deepcopy(BLOCK_V3)
        self.wallet = Wallet()
        signature = self.wallet.sign(encode(self.block))
        self.block['minted'] = {
            'minter': self.wallet.verifying_key,
            'signature': signature
        }

    def test_verify_block__returns_TRUE_if_block_is_valid_OLD_block(self):
        self.assertTrue(block_validator.verify_block(
            block=self.block,
            old_block=True
        ))

    def test_verify_block__returns_TRUE_if_block_is_valid_NEW_block(self):
        self.assertTrue(block_validator.verify_block(
            block=self.block_v3
        ))

    def test_verify_block__returns_FALSE_if_exception_is_raised_OLD_block(self):
        del self.block['hash']
        self.assertFalse(block_validator.verify_block(
            block=self.block,
            old_block=True
        ))

    def test_verify_block__returns_FALSE_if_exception_is_raised_NEW_block(self):
        del self.block_v3['hash']
        self.assertFalse(block_validator.verify_block(
            block=self.block_v3
        ))

    def test_verify_block__returns_FALSE_if_minter_signature_is_malformed(self):
        self.block['minted']['signature'] = 'abc'

        self.assertFalse(block_validator.verify_block(block=self.block))

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

    def test_is_iso8601_hlc_timestamp__returns_True_if_hlc_is_valid(self):
        self.assertTrue(block_validator.is_iso8601_hlc_timestamp("2022-07-06T18:15:00.379629056Z_0"))

    def test_is_iso8601_hlc_timestamp__returns_False_if_hlc_is_not_valid(self):
        self.assertFalse(block_validator.is_iso8601_hlc_timestamp("202207T18:15:00.379629056"))

    def test_validate_block_structure__raises_no_exceptions_if_block_is_valid(self):
        self.assertTrue(block_validator.validate_block_structure(block=self.block))

    def test_validate_block_structure__raises_BlockMintedInvalid(self):
        with self.assertRaises(block_validator.BlockMintedInvalid) as err:
            self.block['minted'] = []
            block_validator.validate_block_structure(block=self.block)

        with self.assertRaises(block_validator.BlockMintedInvalid) as err:
            self.block['minted'] = {}
            block_validator.validate_block_structure(block=self.block)

        with self.assertRaises(block_validator.BlockMintedInvalid) as err:
            self.block['minted'] = {'something': 'something', 'something': 'something'}
            block_validator.validate_block_structure(block=self.block)

        with self.assertRaises(block_validator.BlockMintedInvalid) as err:
            self.block['minted'] = {'minter': 'me', 'something': 'else'}
            block_validator.validate_block_structure(block=self.block)

        with self.assertRaises(block_validator.BlockMintedInvalid) as err:
            self.block['minted'] = {'signature': 'abc', 'something': 'else'}
            block_validator.validate_block_structure(block=self.block)

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

        with self.assertRaises(block_validator.BlockNumberInvalid) as err:
            self.block['number'] = "abc"
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

    def test_validate_block_structure__raises_BlockKeysInvalidNumber(self):
        with self.assertRaises(block_validator.BlockKeysInvalidNumber) as err:
            self.block['testing'] = True
            block_validator.validate_block_structure(block=self.block)

        self.assertEqual(BLOCK_EXCEPTIONS['BlockKeysInvalidNumber'], str(err.exception))

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
        self.assertTrue(block_validator.verify_transaction_signature(transaction=TRANSACTION))

    def test_verify_transaction_signature__testing(self):
        signature = "5e5cbcc7d3331e1f2d983c280fd88fc3bf4ee6582f9a253f4690b75920ce2c02b2d5704b30669d164523dbe2a3153ebd0ec7e12332a3f8f2028590547bcf600c"
        payload = {"contract": "con_testing", "function": "test_values", "kwargs": {"Str": "test string", "UID": "lamdenjs-testing"}, "nonce": 0, "processor": "3d11988757d79e72725bad8998c9437e06228b1eef84d1282f1721187530da06", "sender": "bf06942178b2203b36abec66593a0b84bd9629a33b7c970874cc5850dd62f369", "stamps_supplied": 100}

        self.assertTrue(block_validator.verify_transaction_signature(transaction={
            "metadata": {"signature": signature},
            "payload": payload
        }))

    def test_verify_origin_signature__returns_True_if_signature_valid(self):
        self.assertTrue(block_validator.verify_origin_signature(block=self.block))

    def test_verify_proof_signature_old__returns_True_if_signature_valid(self):
        tx_result = self.block.get('processed')
        rewards = self.block.get('rewards')
        hlc_timestamp = self.block.get('hlc_timestamp')

        proofs = self.block.get('proofs')
        self.assertTrue(block_validator.verify_proof_signature_old(
            proof=proofs[0],
            tx_result=tx_result,
            rewards=rewards,
            hlc_timestamp=hlc_timestamp
        ))

    def test_verify_proof_signature__returns_True_if_signature_valid(self):
        tx_result = self.block_v3.get('processed')
        rewards = self.block_v3.get('rewards')
        hlc_timestamp = self.block_v3.get('hlc_timestamp')

        proofs = self.block_v3.get('proofs')
        self.assertTrue(block_validator.verify_proof_signature(
            proof=proofs[0],
            tx_result=tx_result,
            rewards=rewards,
            hlc_timestamp=hlc_timestamp
        ))

    def test_verify_proofs__returns_True_if_all_signatures_are_valid_OLD_block(self):
        self.assertTrue(block_validator.verify_proofs(block=self.block, old_block=True))

    def test_verify_proofs__returns_True_if_all_signatures_are_valid_NEW_block(self):
        self.assertTrue(block_validator.verify_proofs(block=self.block_v3, old_block=False))

    def test_validate_all_signatures__returns_true_if_all_valid(self):
        self.assertTrue(block_validator.validate_all_signatures(block=self.block))

    def test_validate_all_signatures__raises_TransactionMetadataSignatureMalformed(self):
        with self.assertRaises(block_validator.TransactionMetadataSignatureMalformed) as err:
            self.block['processed']['transaction']['payload']['contract'] = "123"
            block_validator.validate_all_signatures(block=self.block)
        self.assertEqual(PAYLOAD_EXCEPTIONS['TransactionMetadataSignatureMalformed'], str(err.exception))

    def test_validate_all_signatures__raises_BlockOriginSignatureMalformed(self):
        bad_signature = self.wallet.sign('TESTING')
        with self.assertRaises(block_validator.BlockOriginSignatureMalformed) as err:
            self.block['origin']['signature'] = bad_signature
            block_validator.validate_all_signatures(block=self.block)
        self.assertEqual(BLOCK_EXCEPTIONS['BlockOriginSignatureMalformed'], str(err.exception))

    def test_validate_all_proof_signatures__raises_BlockProofMalformed_on_old_block(self):
        # not checking proofs on old blocks
        # This will fail
        bad_proof = {
            'signer': self.wallet.verifying_key,
            'signature': self.wallet.sign(f'TESTING')
        }

        with self.assertRaises(block_validator.BlockProofMalformed) as err:
            self.block['proofs'].append(bad_proof)
            block_validator.validate_all_proof_signatures(block=self.block, old_block=True)
        self.assertEqual(BLOCK_EXCEPTIONS['BlockProofMalformed'], str(err.exception))


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

class TestGenesisBlockValidator(TestCase):
    def setUp(self):
        self.genesis_block = deepcopy(GENESIS_BLOCK)

    def test_verify_block__returns_True_on_valid_genesis_block(self):
        self.assertTrue(block_validator.verify_block(block=self.genesis_block))

    def test_verify_block__returns_False_if_block_raises_exception(self):
        del self.genesis_block['number']
        self.assertFalse(block_validator.verify_block(block=self.genesis_block))

    def test_validate_genesis_hashes__return_True_if_hashes_valid(self):
        self.assertTrue(block_validator.validate_genesis_hashes(block=self.genesis_block))

    def test_validate_genesis_hashes__raises_BlockHashMalformed_exception_if_hashes_invalid(self):
        with self.assertRaises(block_validator.BlockHashMalformed):
            self.genesis_block['hash'] = '0' * 64
            block_validator.validate_genesis_hashes(block=self.genesis_block)

    def test_validate_genesis_signatures__return_True_if_signatures_are_valid(self):
        self.assertTrue(block_validator.validate_genesis_signatures(block=self.genesis_block))

    def test_validate_genesis_signatures__raises_BlockOriginSignatureMalformed_exception_if_hashes_invalid(self):
        with self.assertRaises(block_validator.BlockOriginSignatureMalformed):
            self.genesis_block['genesis'] = []
            block_validator.validate_genesis_signatures(block=self.genesis_block)

    def test_verify_genesis_origin_signature__returns_True_if_signature_valid(self):
        self.assertTrue(block_validator.verify_genesis_origin_signature(block=self.genesis_block))

    def test_verify_genesis_origin_signature__returns_False_if_signature_invalid(self):
        self.genesis_block['origin']['sender'] = '0' * 64
        self.assertFalse(block_validator.verify_genesis_origin_signature(block=self.genesis_block))

    def test_validate_block_structure__raises_GenesisBlockNumberInvalid_not_zero(self):
        with self.assertRaises(block_validator.GenesisBlockNumberInvalid) as err:
            self.genesis_block['number'] = "1"
            block_validator.validate_block_structure(block=self.genesis_block)

        self.assertEqual(BLOCK_EXCEPTIONS['GenesisBlockNumberInvalid'], str(err.exception))

        with self.assertRaises(block_validator.GenesisBlockNumberInvalid) as err:
            self.genesis_block['number'] = "abc"
            block_validator.validate_block_structure(block=self.genesis_block)

        self.assertEqual(BLOCK_EXCEPTIONS['GenesisBlockNumberInvalid'], str(err.exception))

    def test_validate_block_structure__raises_GenesisBlockHLCInvalid(self):
        with self.assertRaises(block_validator.GenesisBlockHLCInvalid) as err:
            self.genesis_block['hlc_timestamp'] = BLOCK_V2['hlc_timestamp']
            block_validator.validate_block_structure(block=self.genesis_block)

        self.assertEqual(BLOCK_EXCEPTIONS['GenesisBlockHLCInvalid'], str(err.exception))

        with self.assertRaises(block_validator.GenesisBlockHLCInvalid) as err:
            del self.genesis_block['hlc_timestamp']
            block_validator.validate_block_structure(block=self.genesis_block)

        self.assertEqual(BLOCK_EXCEPTIONS['GenesisBlockHLCInvalid'], str(err.exception))

    def test_validate_block_structure__raises_GenesisBlockPreviousHashInvalid(self):
        with self.assertRaises(block_validator.GenesisBlockPreviousHashInvalid) as err:
            self.genesis_block['previous'] = BLOCK_V2['previous']
            block_validator.validate_block_structure(block=self.genesis_block)

        self.assertEqual(BLOCK_EXCEPTIONS['GenesisBlockPreviousHashInvalid'], str(err.exception))


    def test_validate_block_structure__raises_GenesisBlockKeysInvalidNumber(self):
        with self.assertRaises(block_validator.GenesisBlockKeysInvalidNumber) as err:
            self.genesis_block['testing'] = True
            block_validator.validate_block_structure(block=self.genesis_block)

        self.assertEqual(BLOCK_EXCEPTIONS['GenesisBlockKeysInvalidNumber'], str(err.exception))