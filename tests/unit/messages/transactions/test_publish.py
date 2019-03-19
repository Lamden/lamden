from unittest import TestCase
from cilantro_ee.messages.transaction.publish import PublishTransaction
from cilantro_ee.protocol import wallet
from decimal import *


class TestPublishTransaction(TestCase):

    def test_creation(self):
        sk, vk = wallet.new()
        kwargs = {'some_text': 'hi', 'some_num': Decimal(1.628), 'some_bool': True}
        gas = 10000
        contract_name = 'smart_contract'
        contract_code = 'submit_contract'
        nonce = vk + ':' + 'A' * 64

        tx = PublishTransaction.create(sender_sk=sk, stamps_supplied=gas, contract_name=contract_name,
                                       contract_code=contract_code, nonce=nonce)

        self.assertEquals(tx.sender, vk)
        self.assertEquals(tx.stamps_supplied, gas)
        self.assertEquals(tx.contract_name, contract_name)
        self.assertEquals(tx.nonce, nonce)

    def test_serialize_deserialize(self):
        sk, vk = wallet.new()
        kwargs = {'some_text': 'hi', 'some_num': Decimal(1.628), 'some_bool': True}
        gas = 10000
        contract_name = 'smart_contract'
        contract_code = 'submit_contract'
        nonce = vk + ':' + 'A' * 64

        tx = PublishTransaction.create(sender_sk=sk, stamps_supplied=gas, contract_name=contract_name,
                                       contract_code=contract_code, nonce=nonce)
        clone = PublishTransaction.from_bytes(tx.serialize())

        self.assertEqual(clone, tx)

