from cilantro.messages import MessageBaseJson
import json


class NewBlockNotification(MessageBaseJson):
    """
    _data is just a string containing the new block hash
    """
    B_HASH = 'block_hash'
    B_NUM = 'block_num'

    def validate(self):
        pass

    @classmethod
    def create(cls, new_block_hash: str, new_block_num: int):
        # TODO validate hash
        data = {cls.B_HASH: new_block_hash, cls.B_NUM: new_block_num}
        return cls.from_data(data)

    @property
    def block_hash(self):
        return self._data[self.B_HASH]

    @property
    def block_num(self):
        return self._data[self.B_NUM]
