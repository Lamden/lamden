from cilantro.protocol.interpreters import SenecaInterpreter
from cilantro.db import reset_db, DB, ContractTemplate
from cilantro.db.contracts import get_contract_exports
from cilantro.messages import ContractTransaction, ContractTransactionBuilder
import unittest
from unittest import TestCase

# These VKs are seeded in the currency.seneca contract
ALICE_SK, ALICE_VK = "20b577e71e0c3bddd3ae78c0df8f7bb42b29b0c0ce9ca42a44e6afea2912d17b", "0c998fa1b2675d76372897a7d9b18d4c1fbe285dc0cc795a50e4aad613709baf"
BOB_SK, BOB_VK = "5664ec7306cc22e56820ae988b983bdc8ebec8246cdd771cfee9671299e98e3c", "ab59a17868980051cc846804e49c154829511380c119926549595bf4b48e2f85"
CARLOS_SK, CARLOS_VK = "8ddaf072b9108444e189773e2ddcb4cbd2a76bbf3db448e55d0bfc131409a197", "3dd5291906dca320ab4032683d97f5aa285b6491e59bba25c958fc4b0de2efc8"

class TestSenecaInterpreter(TestCase):

    @classmethod
    def setUpClass(cls):
        reset_db()

    def test_init(self):
        interpreter = SenecaInterpreter()  # this should not blow up
        self.assertTrue(interpreter.ex is not None)
        self.assertTrue(interpreter.contracts_table is not None)

    def test_interpret_currency(self):
        amount = 1260
        receiver = BOB_VK
        sender = ALICE_VK
        contract_tx = ContractTransactionBuilder.create_currency_tx(sender_sk=ALICE_SK, receiver_vk=receiver, amount=amount)

        interpreter = SenecaInterpreter()
        currency_contract = get_contract_exports(interpreter.ex, interpreter.contracts_table, contract_id='currency')

        sender_initial_balance = currency_contract.get_balance(sender)
        receiver_initial_balance = currency_contract.get_balance(receiver)

        interpreter.interpret(contract_tx)

        # Assert the contract ran and updated the expected rows
        self.assertEquals(currency_contract.get_balance(sender), sender_initial_balance - amount)
        self.assertEquals(currency_contract.get_balance(receiver), receiver_initial_balance + amount)

        # Assert the contract was added to the queue
        self.assertEquals(interpreter.queue_size, 1)
        self.assertEquals(interpreter.queue[0], contract_tx)

    def test_run_bad_contract_not_in_queue(self):
        """
        Tests that interpretting a bad contract does not get added to the queue
        """
        # TODO implement
        pass

    def test_run_bad_contract_reverts_partial_changes(self):
        """
        Tests that running a failing contract reverts any database changes it made before the point of failure
        """
        # TODO implement
        # NOTE this will require some engineering in the SenecaInterpreter class as well
        pass

    def test_run_goods_then_bads(self):
        """
        Tests running a bunch of good/passing contracts, and then a single bad one. The bad one should be reverted,
        and the 'state' should be rolled back to before the failing contract was executed.

        For example, say we run a chain of successful contract S_n, ie
        S_1, S_2, S_3
        ...And then we run a failing contract B_1, so the chain of execution looks like:
        S_1, S_2, S_3, B_1
        ...Upon realizing B_1 fails, the state should be rollbacked to look like:
        S_1, S_2, S_3
        """
        # TODO implement
        # NOTE this will require some engineering in the SenecaInterpreter class as well
        pass

    def test_interpret_invalid_type(self):
        interpreter = SenecaInterpreter()
        not_a_contract = 'sup bro im a string'

        self.assertRaises(AssertionError, interpreter.interpret, not_a_contract)

    def test_flushes_with_update(self):
        """
        Tests that calling .flush on an interpreter with update_state=True after interpreting several transactions
        successfully commits the changes to the database
        """
        # TODO implement
        pass

    def test_flushes_without_update(self):
        """
        Tests that calling .flush on an interpreter with update_state=False after interpreting several transactions
        successfully rolls back
        """
        # TODO implement
        pass
    
    def test_queue_binary(self):
        """
        Tests that queue_binary returns a list of serialized ContractTransactions
        """
        # TODO implement
        pass

    def test_queue_binary_with_bad_contracts(self):
        """
        Same test as above (test_queue_binary), except with interpreting some contracts that fail
        """
        # TODO implement
        pass


if __name__ == '__main__':
    unittest.main()