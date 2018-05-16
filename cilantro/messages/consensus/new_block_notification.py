from cilantro.messages import MessageBaseJson
import json


class NewBlockNotification(MessageBaseJson):
    """
    _data is just a string containing the new block hash
    """
    B_HASH = 'block_hash'

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

    def __eq__(self, other):
        return self.block_hash == other.block_hash
