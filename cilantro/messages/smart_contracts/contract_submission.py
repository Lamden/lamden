from cilantro.messages import MessageBaseJson


class ContractSubmission(MessageBaseJson):

    USER_ID = 'user_id'
    CONTRACT_CODE = 'contract_code'

    def validate(self):
        pass

    @classmethod
    def create(cls, user_id: str, contract_code: str):
        data = {cls.USER_ID: user_id, cls.CONTRACT_CODE: contract_code}

        return cls.from_data(data)

    @property
    def user_id(self):
        return self._data[self.USER_ID]

    @property
    def contract_code(self):
        return self._data[self.CONTRACT_CODE]
