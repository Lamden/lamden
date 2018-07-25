from cilantro.protocol.interpreters import SenecaInterpreter
from cilantro.db import reset_db, DB, ContractTemplate
from cilantro.db.contracts import get_contract_exports
from cilantro.messages import ContractTransaction, ContractTransactionBuilder, OrderingContainer
import unittest, time
from heapq import heappush, heappop
from unittest import TestCase
from cilantro.utils.test.async_utils import async_run_for
from threading import Timer

# These VKs are seeded in the currency.seneca contract
MN_VK = "82540bb5a9c84162214c5540d6e43be49bbfe19cf49685660cab608998a65144"
ALICE_SK, ALICE_VK = "20b577e71e0c3bddd3ae78c0df8f7bb42b29b0c0ce9ca42a44e6afea2912d17b", "0c998fa1b2675d76372897a7d9b18d4c1fbe285dc0cc795a50e4aad613709baf"
BOB_SK, BOB_VK = "5664ec7306cc22e56820ae988b983bdc8ebec8246cdd771cfee9671299e98e3c", "ab59a17868980051cc846804e49c154829511380c119926549595bf4b48e2f85"
CARLOS_SK, CARLOS_VK = "8ddaf072b9108444e189773e2ddcb4cbd2a76bbf3db448e55d0bfc131409a197", "3dd5291906dca320ab4032683d97f5aa285b6491e59bba25c958fc4b0de2efc8"

class TestSenecaInterpreter(TestCase):

    def setUp(self):
        reset_db()

    def ordered_tx(self, contract):
        return OrderingContainer.create(contract, MN_VK)

    def test_init(self):
        interpreter = SenecaInterpreter()  # this should not blow up
        self.assertTrue(interpreter.ex is not None)
        self.assertTrue(interpreter.contracts_table is not None)

    def test_interpret_invalid_type(self):
        interpreter = SenecaInterpreter()
        not_a_contract = 'sup bro im a string'

        self.assertRaises(AssertionError, interpreter.interpret, not_a_contract)

    def test_interpret_currency(self):
        amount = 1260
        receiver = BOB_VK
        sender = ALICE_VK
        contract_tx = self.ordered_tx(ContractTransactionBuilder.create_currency_tx(sender_sk=ALICE_SK, receiver_vk=receiver, amount=amount))

        interpreter = SenecaInterpreter()
        currency_contract = get_contract_exports(interpreter.ex, interpreter.contracts_table, contract_id='currency')

        sender_initial_balance = currency_contract.get_balance(sender)
        receiver_initial_balance = currency_contract.get_balance(receiver)

        interpreter.interpret(contract_tx)

        # Assert the contract ran and updated the expected rows
        self.assertEqual(currency_contract.get_balance(sender), sender_initial_balance - amount)
        self.assertEqual(currency_contract.get_balance(receiver), receiver_initial_balance + amount)

        # Assert the contract was added to the queue
        self.assertEqual(interpreter.queue_size, 1)
        self.assertEqual(interpreter.queue[0], contract_tx.transaction)

    def test_run_bad_contract_reverts_to_last_successful_contract(self):
        """
        Tests that running a failing contract reverts any database changes it made before the point of failure
        """
        receiver = BOB_VK
        sender = ALICE_VK

        interpreter = SenecaInterpreter()
        currency_contract = get_contract_exports(interpreter.ex, interpreter.contracts_table, contract_id='currency')

        sender_initial_balance = currency_contract.get_balance(sender)
        contract_tx = self.ordered_tx(ContractTransactionBuilder.create_currency_tx(sender_sk=ALICE_SK, receiver_vk=receiver, amount=1000))
        interpreter.interpret(contract_tx)
        self.assertEqual(currency_contract.get_balance(sender), sender_initial_balance - 1000)
        contract_tx = self.ordered_tx(ContractTransactionBuilder.create_currency_tx(sender_sk=ALICE_SK, receiver_vk=receiver, amount=200))
        interpreter.interpret(contract_tx)
        self.assertEqual(currency_contract.get_balance(sender), sender_initial_balance - 1200)
        contract_tx = self.ordered_tx(ContractTransactionBuilder.create_currency_tx(sender_sk=ALICE_SK, receiver_vk=receiver, amount=60))
        interpreter.interpret(contract_tx)
        self.assertEqual(currency_contract.get_balance(sender), sender_initial_balance - 1260)

        contract_tx = self.ordered_tx(ContractTransactionBuilder.create_currency_tx(sender_sk=ALICE_SK, receiver_vk=receiver, amount=3696947))
        interpreter.interpret(contract_tx)
        self.assertEqual(currency_contract.get_balance(sender), sender_initial_balance - 1260)

    def test_run_bad_contract_reverts_to_last_successful_contract_remove_partial(self):
        """
        Tests that running a failing contract reverts any database changes it made before the point of failure
        """
        sender = ALICE_VK
        receiver = BOB_VK

        interpreter = SenecaInterpreter()
        dummy_contract = get_contract_exports(interpreter.ex, interpreter.contracts_table, contract_id='dummy')

        sender_initial_balance = dummy_contract.get_balance(sender)
        self.assertEqual(dummy_contract.get_balance(sender), sender_initial_balance)
        contract_tx = self.ordered_tx(ContractTransactionBuilder.create_dummy_tx(sender_sk=ALICE_SK, receiver_vk=receiver, fail=False))
        interpreter.interpret(contract_tx)
        self.assertEqual(dummy_contract.get_balance(sender), sender_initial_balance + 500)
        # NOTE it attempts to update the balance to 123 and add the same user again
        #   Updating should work and adding already added user
        contract_tx = self.ordered_tx(ContractTransactionBuilder.create_dummy_tx(sender_sk=ALICE_SK, receiver_vk=receiver, fail=True))
        interpreter.interpret(contract_tx)
        self.assertEqual(dummy_contract.get_balance(sender), sender_initial_balance + 500)

    def test_flushes_with_update(self):
        """
        Tests that calling .flush on an interpreter with update_state=True after interpreting several transactions
        successfully commits the changes to the database
        """
        sender = ALICE_VK
        receiver = BOB_VK

        interpreter = SenecaInterpreter()
        dummy_contract = get_contract_exports(interpreter.ex, interpreter.contracts_table, contract_id='dummy')

        sender_initial_balance = dummy_contract.get_balance(sender)
        contract_tx = self.ordered_tx(ContractTransactionBuilder.create_dummy_tx(sender_sk=ALICE_SK, receiver_vk=receiver, fail=False))
        interpreter.interpret(contract_tx)
        self.assertEqual(dummy_contract.get_balance(sender), sender_initial_balance + 500)
        contract_tx = self.ordered_tx(ContractTransactionBuilder.create_dummy_tx(sender_sk=ALICE_SK, receiver_vk=receiver, fail=False))
        interpreter.interpret(contract_tx)
        interpreter.flush(update_state=True)
        self.assertEqual(dummy_contract.get_balance(sender), sender_initial_balance + 1000)

    def test_flushes_without_update(self):
        """
        Tests that calling .flush on an interpreter with update_state=False after interpreting several transactions
        successfully rolls back
        """
        sender = ALICE_VK
        receiver = BOB_VK

        interpreter = SenecaInterpreter()
        dummy_contract = get_contract_exports(interpreter.ex, interpreter.contracts_table, contract_id='dummy')

        sender_initial_balance = dummy_contract.get_balance(sender)
        contract_tx = self.ordered_tx(ContractTransactionBuilder.create_dummy_tx(sender_sk=ALICE_SK, receiver_vk=receiver, fail=False))
        interpreter.interpret(contract_tx)
        contract_tx = self.ordered_tx(ContractTransactionBuilder.create_dummy_tx(sender_sk=ALICE_SK, receiver_vk=receiver, fail=False))
        interpreter.interpret(contract_tx)
        interpreter.flush(update_state=True)
        self.assertEqual(dummy_contract.get_balance(sender), sender_initial_balance + 1000)

        contract_tx = self.ordered_tx(ContractTransactionBuilder.create_dummy_tx(sender_sk=ALICE_SK, receiver_vk=receiver, fail=False))
        interpreter.interpret(contract_tx)
        self.assertEqual(dummy_contract.get_balance(sender), sender_initial_balance + 1500)
        interpreter.flush(update_state=False)
        self.assertEqual(dummy_contract.get_balance(sender), sender_initial_balance + 1000)

    def test_queue_binary(self):
        """
        Tests that queue_binary returns a list of serialized ContractTransactions
        """
        sender = ALICE_VK
        receiver = BOB_VK

        interpreter = SenecaInterpreter()
        dummy_contract = get_contract_exports(interpreter.ex, interpreter.contracts_table, contract_id='dummy')

        contracts = []
        for i in range(5):
            contract_tx = self.ordered_tx(ContractTransactionBuilder.create_dummy_tx(sender_sk=ALICE_SK, receiver_vk=receiver, fail=False))
            interpreter.interpret(contract_tx)
            contracts.append(contract_tx.transaction)

        for actual, expected in zip([c.serialize() for c in contracts], interpreter.queue_binary):
            self.assertEqual(actual, expected)

    def test_check_contract_correct_order(self):
        sender = ALICE_VK
        receiver = BOB_VK
        now = int(time.time()*1000)

        interpreter = SenecaInterpreter()
        contracts = [
            self.ordered_tx(ContractTransactionBuilder.create_dummy_tx(sender_sk=ALICE_SK, receiver_vk=receiver, fail=False)) \
            for i in range(5)
        ]
        contracts[0]._data.utcTimeMs = now - 2000
        contracts[1]._data.utcTimeMs = now - 1000
        contracts[2]._data.utcTimeMs = now
        contracts[3]._data.utcTimeMs = now + 1000
        contracts[4]._data.utcTimeMs = now + 2000

        for c in contracts:
            interpreter.interpret(c, async=True)

        self.assertEqual(contracts, [heappop(interpreter.heap)[1] for i in range(5)])

    def test_check_contract_correct_order_shuffled(self):
        sender = ALICE_VK
        receiver = BOB_VK
        now = int(time.time()*1000)

        interpreter = SenecaInterpreter()
        contracts = [
            self.ordered_tx(ContractTransactionBuilder.create_dummy_tx(sender_sk=ALICE_SK, receiver_vk=receiver, fail=False)) \
            for i in range(5)
        ]
        contracts[0]._data.utcTimeMs = now - 2000
        contracts[1]._data.utcTimeMs = now - 1000
        contracts[2]._data.utcTimeMs = now + 1000
        contracts[3]._data.utcTimeMs = now
        contracts[4]._data.utcTimeMs = now - 3000

        for c in contracts:
            interpreter.interpret(c, async=True)

        self.assertEqual(contracts[4], heappop(interpreter.heap)[1])
        self.assertEqual(contracts[0], heappop(interpreter.heap)[1])
        self.assertEqual(contracts[1], heappop(interpreter.heap)[1])
        self.assertEqual(contracts[3], heappop(interpreter.heap)[1])
        self.assertEqual(contracts[2], heappop(interpreter.heap)[1])

    @async_run_for(4)
    def test_check_contract_async_shuffled_adhoc_checks(self, loop):

        def assertCondition():
            self.assertEqual(contracts[0].transaction, interpreter.queue[0])
            self.assertEqual(contracts[2].transaction, interpreter.queue[1])
            self.assertEqual(contracts[1].transaction, interpreter.queue[2])
            self.assertEqual(contracts[3].transaction, interpreter.queue[3])
            self.assertEqual(contracts[4].transaction, interpreter.queue[4])

        sender = ALICE_VK
        receiver = BOB_VK
        now = int(time.time()*1000)

        interpreter = SenecaInterpreter(loop)
        contracts = [
            self.ordered_tx(ContractTransactionBuilder.create_dummy_tx(sender_sk=ALICE_SK, receiver_vk=receiver, fail=False)) \
            for i in range(5)
        ]
        contracts[0]._data.utcTimeMs = now - 2000
        contracts[1]._data.utcTimeMs = now
        contracts[2]._data.utcTimeMs = now - 1000
        contracts[3]._data.utcTimeMs = now + 1000
        contracts[4]._data.utcTimeMs = now + 2000

        for c in contracts:
            interpreter.interpret(c, async=True)

        t = Timer(4, assertCondition)
        t.start()




if __name__ == '__main__':
    unittest.main()
