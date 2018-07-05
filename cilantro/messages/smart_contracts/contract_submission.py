from cilantro.messages import MessageBaseJson
from cilantro.utils import Hasher


class ContractSubmission(MessageBaseJson):

    USER_ID = 'user_id'
    CONTRACT_CODE = 'contract_code'
    CONTRACT_ID = 'contract_id'

    def validate(self):
        pass

    @classmethod
    def user_create(cls, user_id: str, contract_code: str):
        data = {cls.USER_ID: user_id, cls.CONTRACT_CODE: contract_code}

        return cls.from_data(data)

    @classmethod
    def node_create(cls, user_id: str, contract_code: str, block_hash: str):
        contract_id = Hasher.hash(user_id + contract_code + block_hash)
        data = {cls.USER_ID: user_id, cls.CONTRACT_CODE: contract_code, cls.CONTRACT_ID: contract_id}

        return cls.from_data(data)

    @property
    def user_id(self):
        return self._data[self.USER_ID]

    @property
    def contract_code(self):
        return self._data[self.CONTRACT_CODE]

    @property
    def contract_id(self):
        return self._data.get(self.CONTRACT_ID)
