from cilantro.messages import MessageBaseJson


class ContractContainer(MessageBaseJson):
    SENDER_ID = 'sender_id'
    CONTRACT_ID = 'contract_id'
    KWARGS = 'kwargs'

    def validate(self):
        assert self.SENDER_ID in self._data, "sender_id key missing from _data"
        assert self.CONTRACT_ID in self._data, "contract_id key missing from _data"
        assert self.KWARGS in self._data, "kwargs key missing from _data"

    @classmethod
    def create(cls, contract_id: str, sender_id: str, **kwargs):
        data = {cls.SENDER_ID: sender_id, cls.CONTRACT_ID: contract_id, cls.KWARGS: kwargs}
        return cls.from_data(data)

    @property
    def kwargs(self):
        return self._data[self.KWARGS]

    @property
    def sender_id(self):
        return self._data[self.SENDER_ID]

    @property
    def contract_id(self):
        return self._data[self.CONTRACT_ID]
