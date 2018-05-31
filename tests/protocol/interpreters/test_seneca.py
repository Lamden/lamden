from cilantro.protocol.interpreters import SenecaInterpreter
from cilantro.messages import *
from unittest import TestCase


class TestSenecaInterpreter(TestCase):

    def test_interpret_submission(self):
        interpreter = SenecaInterpreter()

        submission = ContractSubmission.node_create(user_id='its me', contract_code='while True: pass', block_hash='00')

        interpreter.interpret(submission)
