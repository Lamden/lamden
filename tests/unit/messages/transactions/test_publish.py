from unittest import TestCase
from cilantro.messages.transaction.publish import PublishTransaction
from cilantro.protocol import wallet
from decimal import *


class TestPublishTransaction(TestCase):

    def test_creation(self):
        sk, vk = wallet.new()
        kwargs = {'some_text': 'hi', 'some_num': Decimal(1.628), 'some_bool': True}
        gas = 10000
        contract_name = 'currency'
        contract_code = 'transfer'
        nonce = vk + ':' + 'A' * 64

        tx = PublishTransaction.create(sender_sk=sk, gas_supplied=gas, contract_name=contract_name,
                                       contract_code=contract_code, nonce=nonce)

        self.assertEquals(tx.sender, vk)
        self.assertEquals(tx.gas_supplied, gas)
        self.assertEquals(tx.contract_name, contract_name)
        self.assertEquals(tx.contract_code, contract_code)
        self.assertEquals(tx.nonce, nonce)

    def test_serialize_deserialize(self):
        sk, vk = wallet.new()
        kwargs = {'some_text': 'hi', 'some_num': Decimal(1.628), 'some_bool': True}
        gas = 10000
        contract_name = 'currency'
        contract_code = 'transfer'
        nonce = vk + ':' + 'A' * 64

        tx = PublishTransaction.create(sender_sk=sk, gas_supplied=gas, contract_name=contract_name,
                                       contract_code=contract_code, nonce=nonce)
        clone = PublishTransaction.from_bytes(tx.serialize())

        self.assertEqual(clone, tx)

