from unittest import TestCase
from cilantro.messages import ContractTransaction, ContractTransactionBuilder
from cilantro.protocol.wallets import ED25519Wallet
from cilantro.db import ContractTemplate


class TestContractTransaction(TestCase):

    def test_creation(self):
        sk, vk = ED25519Wallet.new()
        code = 'while True: do_that_thing'

        contract_tx = ContractTransactionBuilder.create_contract_tx(sender_sk=sk, code_str=code)

        self.assertEquals(contract_tx.sender, vk)
        self.assertEquals(contract_tx.code, code)

    def test_create_currency_tx(self):
        sk, vk = ED25519Wallet.new()
        sk2, vk2 = ED25519Wallet.new()
        amount = 9000
        currency_code = ContractTemplate.interpolate_template('currency', amount=amount, receiver=vk2)

        contract_tx = ContractTransactionBuilder.create_currency_tx(sender_sk=sk, receiver_vk=vk2, amount=amount)

        self.assertEquals(contract_tx.sender, vk)
        self.assertEquals(contract_tx.code, currency_code)



