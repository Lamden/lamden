from cilantro.protocol.interpreters import SenecaInterpreter
from cilantro.db import reset_db, DB
from cilantro.messages import *
import unittest
from unittest import TestCase


class TestSenecaInterpreter(TestCase):

    @classmethod
    def setUpClass(cls):
        reset_db()

    def test_init(self):
        interpreter = SenecaInterpreter()  # this should not blow up
        self.assertTrue(interpreter.ex is not None)
        self.assertTrue(interpreter.contracts_table is not None)

    def test_interpret_currency(self):
        pass

    def test_interpet_not_contract(self):
        interpreter = SenecaInterpreter()  # this should not blow up
        not_a_contract = 'sup bro im a string'

        self.assertRaises(AssertionError, interpreter.interpret, not_a_contract)

if __name__ == '__main__':
    unittest.main()