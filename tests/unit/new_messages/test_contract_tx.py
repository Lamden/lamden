from cilantro_ee.messages._new.transactions.messages import ContractTransaction
from unittest import TestCase


class TestContractTransaction(TestCase):
    def test_init(self):
        ContractTransaction('blah', 123, 'blah', 'blah', 'blah', {'something': 123})