from cilantro.messages import MessageBase
import json


class NewBlockNotification(MessageBase):
    """
    _data is just a string containing the new block hash
    """
    B_HASH = 'block_hash'

    @classmethod
    def _deserialize_data(cls, data: bytes):
        return json.loads(data)

    def serialize(self):
        return json.dumps(self._data)

    def validate(self):
        pass

    @classmethod
    def create(cls, new_block_hash: str):
        # TODO validate hash
        data = {cls.B_HASH: new_block_hash}
        return cls.from_data(data)

    @property
    def block_hash(self):
        return self._data[self.B_HASH]