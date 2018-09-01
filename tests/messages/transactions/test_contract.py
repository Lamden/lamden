from unittest import TestCase
from cilantro.messages.transaction.contract import ContractTransactionBuilder
from cilantro.protocol import wallet
from cilantro.storage.templating import ContractTemplate


class TestContractTransaction(TestCase):

    def test_creation(self):
        sk, vk = wallet.new()
        code = 'while True: do_that_thing'

        contract_tx = ContractTransactionBuilder.create_contract_tx(sender_sk=sk, code_str=code)

        self.assertEquals(contract_tx.sender, vk)
        self.assertEquals(contract_tx.code, code)

    def test_create_currency_tx(self):
        sk, vk = wallet.new()
        sk2, vk2 = wallet.new()
        amount = 9000
        currency_code = ContractTemplate.interpolate_template('currency', amount=amount, receiver=vk2)

        contract_tx = ContractTransactionBuilder.create_currency_tx(sender_sk=sk, receiver_vk=vk2, amount=amount)

        self.assertEquals(contract_tx.sender, vk)
        self.assertEquals(contract_tx.code, currency_code)



