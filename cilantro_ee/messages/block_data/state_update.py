from cilantro_ee.messages.base.base_json import MessageBaseJson
from typing import List

class BlockIndexReply(MessageBaseJson):
    def validate(self):
        # TODO do validation logic here, not in create
        pass

    @classmethod
    def create(cls, block_info: List[dict]):
        return cls.from_data(block_info)

    @property
    def indices(self) -> List[dict]:
        return self._data

