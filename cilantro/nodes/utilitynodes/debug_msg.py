
from cilantro.messages import MessageBase
import pickle

class DebugMsg(MessageBase):
    def validate(self):
        assert type(self._data) == str, "DebugMsg's _data must be a str"

    def serialize(self):
        return pickle.dumps(self._data)

    @classmethod
    def _deserialize_data(cls, data: bytes):
        return pickle.loads(data)
