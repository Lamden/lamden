from cilantro.messages import ContractContainer
from unittest import TestCase


class TestContractContainer(TestCase):

    def test_init(self):
        contract_id = 'A' * 64
        sender_id = 'B' * 64

        arg1 = 'hello'
        arg2 = 12

        contract = ContractContainer.create(contract_id=contract_id, sender_id=sender_id, arg1=arg1, arg2=arg2)

        self.assertTrue()

    def test_properties(self):
        contract_id = 'A' * 64
        sender_id = 'B' * 64

        contract = ContractContainer.create(contract_id=contract_id, sender_id=sender_id)

        self.assertEquals(contract.sender_id, sender_id)
        self.assertEquals(contract.contract_id, contract_id)

    def test_kwargs(self):
        contract_id = 'A' * 64
        sender_id = 'B' * 64

        arg1 = 'hello'
        arg2 = 12

        contract = ContractContainer.create(contract_id=contract_id, sender_id=sender_id, arg1=arg1, arg2=arg2)

        self.assertEquals(contract.kwargs['arg1'], arg1)
        self.assertEquals(contract.kwargs['arg2'], arg2)
        self.assertEquals(contract.sender_id, sender_id)
        self.assertEquals(contract.contract_id, contract_id)

    def test_serializiation(self):
        contract_id = 'A' * 64
        sender_id = 'B' * 64

        arg1 = 'hello'
        arg2 = 12

        contract = ContractContainer.create(contract_id=contract_id, sender_id=sender_id, arg1=arg1, arg2=arg2)
        contract_binary = contract.serialize()

        clone = ContractContainer.from_bytes(contract_binary)

        self.assertEqual(clone, contract)

