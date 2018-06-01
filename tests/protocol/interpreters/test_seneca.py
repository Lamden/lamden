from cilantro.protocol.interpreters import SenecaInterpreter
from cilantro.messages import *
import unittest
from unittest import TestCase


class TestSenecaInterpreter(TestCase):

    def test_interpret_submission(self):
        interpreter = SenecaInterpreter()

        submission = ContractSubmission.node_create(user_id='its me', contract_code='while True: pass', block_hash='00')

        interpreter.interpret(submission)

        # q = interpreter.contract_table.select().run(interpreter.ex)

        lookup = interpreter.get_contract_code(submission.contract_id)
        # q.keys is an array of keys (the columns)
        # q.rows is a list of tuples, where each tuple is a row
        # print("got query: \n"
        #       "{}".format(q))

if __name__ == '__main__':
    unittest.main()