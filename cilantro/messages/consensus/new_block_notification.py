from cilantro.messages import MessageBaseJson


class NewBlockNotification(MessageBaseJson):
    """
    NewBlockNotifications are published by Masternodes to all delegates once a new block has been published. They simply
    inform delegates that a new block has been published. To retrieve the latest block data, Delegates will have to request
    StateUpdateRequests from a Masternode.
    """
    B_HASH = 'block_hash'
    B_NUM = 'block_num'

    def validate(self):
        # TODO validate hash
        pass

    @classmethod
    def create(cls, new_block_hash: str, new_block_num: int):
        data = {cls.B_HASH: new_block_hash, cls.B_NUM: new_block_num}
        return cls.from_data(data)

    @property
    def block_hash(self) -> str:
        """
        The hash of the new block
        """
        return self._data[self.B_HASH]

    @property
    def block_num(self):
        """
        The number of the new block
        """
        return self._data[self.B_NUM]
