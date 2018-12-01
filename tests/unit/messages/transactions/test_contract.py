from unittest import TestCase
from cilantro.messages.transaction.contract import ContractTransactionBuilder
from cilantro.messages.transaction.contract import ContractTransaction
from cilantro.protocol import wallet
from decimal import *


class TestContractTransaction(TestCase):

    def test_creation(self):
        sk, vk = wallet.new()
        kwargs = {'some_text': 'hi', 'some_num': Decimal(1.628), 'some_bool': True}
        gas = 10000
        contract_name = 'currency'
        func_name = 'transfer'

        contract_tx = ContractTransaction.create(sender_sk=sk, stamps=gas, contract_name=contract_name,
                                                 func_name=func_name, **kwargs)

        self.assertEquals(contract_tx.sender, vk)
        self.assertEquals(contract_tx.stamps, gas)
        self.assertEquals(contract_tx.contract_name, contract_name)
        self.assertEquals(contract_tx.func_name, func_name)

    def test_serialize_deserialize(self):
        sk, vk = wallet.new()
        kwargs = {'some_text': 'hi', 'some_num': Decimal(1.628), 'some_bool': True}
        gas = 10000
        contract_name = 'currency'
        func_name = 'transfer'

        contract_tx = ContractTransaction.create(sender_sk=sk, stamps=gas, contract_name=contract_name,
                                                 func_name=func_name, **kwargs)
        clone = ContractTransaction.from_bytes(contract_tx.serialize())

        self.assertEqual(clone, contract_tx)

    def test_kwargs(self):
        sk, vk = wallet.new()
        kwargs = {'some_text': 'hi', 'some_num': Decimal(1.628), 'some_bool': True}
        gas = 10000
        contract_name = 'currency'
        func_name = 'transfer'

        contract_tx = ContractTransaction.create(sender_sk=sk, stamps=gas, contract_name=contract_name,
                                                 func_name=func_name, **kwargs)

        self.assertEqual(contract_tx.kwargs, kwargs)

    def test_create_currency_tx(self):
        sk, vk = wallet.new()
        sk2, vk2 = wallet.new()
        amount = Decimal(9000.123456)

        contract_tx = ContractTransactionBuilder.create_currency_tx(sender_sk=sk, receiver_vk=vk2, amount=amount)

        self.assertEquals(contract_tx.sender, vk)
        self.assertEquals(contract_tx.kwargs['to'], vk2)
        self.assertEquals(contract_tx.kwargs['amount'], amount)

        clone = ContractTransaction.from_bytes(contract_tx.serialize())
        self.assertEqual(contract_tx, clone)


