from cilantro.messages import MessageBase
from cilantro.messages.consensus.block_contender import BlockContender
from cilantro.messages.utils import validate_hex
from cilantro.utils import lazy_property
from typing import List

import capnp
import blockdata_capnp


class BlockMetaData(MessageBase):
    """
    This class acts a structure that holds all information necessary to validate and build a block. In particular, this
    means the information carried in this class provide everything an actor needs to insert a new entry into the
    'blocks' table (see schema specified in db/blocks.py). It DOES NOT contain the actual transactions associated with
    a block, but rather the Merkle leaves of the block (ie hashes of the block's transactions). After a delegate
    parses this class, it must request a TransactionRequest to get the actual raw transaction data.
    """

    def validate(self):
        assert validate_hex(self._data.hash, 64), 'Invalid hash'
        assert validate_hex(self._data.prevBlockHash, 64), 'Invalid previous block hash'
        assert validate_hex(self._data.merkleRoot, 64), 'Invalid merkle root'
        assert len(self._data.merkleLeaves) % 64 == 0, 'Invalid merkle leaves'
        assert validate_hex(self._data.masternodeSignature, 128), 'Invalid masternode signature'
        assert validate_hex(self._data.masternodeVk, 64), 'Invalid masternode vk'
        assert type(self._data.timestamp) == int, 'Invalid timestamp'
        self.validate_block_data()

    def validate_block_data(self):
        """
        Attempts to validate the block data, raising an Exception if any fields are invalid.
        See BlockStorageDriver.validate_block_data for validation details.
        :return: None
        :raises: An exception if validation fails
        """
        from cilantro.db.blocks import BlockStorageDriver  # imported here to avoid cyclic import (im so sorry --davis)

        block_data = self.block_dict()
        actual_hash = block_data.pop('hash')

        BlockStorageDriver.validate_block_data(block_data)
        assert actual_hash == self.block_hash, "Computed block hash {} does not match self.block_hash {}"\
                                               .format(actual_hash, self.block_hash)

    @classmethod
    def _deserialize_data(cls, data: bytes):
        return blockdata_capnp.BlockMetaData.from_bytes_packed(data)

    @classmethod
    def create(cls, hash: str, merkle_root: str, merkle_leaves: str, prev_block_hash: str, timestamp: int,
               masternode_signature: str, masternode_vk: str, block_contender: BlockContender):
        struct = blockdata_capnp.BlockMetaData.new_message()
        struct.hash = hash
        struct.merkleRoot = merkle_root
        struct.merkleLeaves = merkle_leaves
        struct.prevBlockHash = prev_block_hash
        struct.timestamp = timestamp
        struct.masternodeSignature = masternode_signature
        struct.masternodeVk = masternode_vk
        assert type(block_contender) == BlockContender, 'Not a block contender'
        struct.blockContender = block_contender.serialize()
        return cls.from_data(struct)

    @classmethod
    def _chunks(cls, l, n=64):
        for i in range(0, len(l), n):
            yield l[i:i + n]

    def block_dict(self):
        """
        A utility property for building a dictionary with keys for each column in the 'blocks' table. This is used to
        facilitate interaction with BlockStorageDriver
        :param include_hash: True if the 'hash' key should be included in the block dictionary.
        :return: A dictionary, containing a key for each column in the blocks table. The 'hash' column can be omitted
        by passing include_hash=False
        """
        from cilantro.db.blocks import BlockStorageDriver  # imported here to avoid cyclic import (im so sorry --davis)

        block_data = {
            'block_contender': self.block_contender,
            'timestamp': self.timestamp,
            'merkle_root': self.merkle_root,
            'merkle_leaves': self._data.merkleLeaves.decode(),
            'prev_block_hash': self.prev_block_hash,
            'masternode_signature': self.masternode_signature,
            'masternode_vk': self.masternode_vk,
        }
        block_data['hash'] = BlockStorageDriver.compute_block_hash(block_data)

        return block_data

    @property
    def block_hash(self) -> str:
        return self._data.hash.decode()

    @property
    def merkle_root(self) -> str:
        return self._data.merkleRoot.decode()

    @lazy_property
    def merkle_leaves(self) -> List[str]:
        return [leaf.decode() for leaf in BlockMetaData._chunks(self._data.merkleLeaves)]

    @property
    def prev_block_hash(self) -> str:
        return self._data.prevBlockHash.decode()

    @property
    def timestamp(self) -> int:
        return self._data.timestamp

    @property
    def masternode_signature(self) -> str:
        return self._data.masternodeSignature.decode()

    @property
    def masternode_vk(self) -> str:
        return self._data.masternodeVk.decode()

    @lazy_property
    def block_contender(self) -> BlockContender:
        return BlockContender.from_bytes(self._data.blockContender)


class NewBlockNotification(BlockMetaData):
    pass


class BlockMetaDataRequest(MessageBase):
    """
    This class represents a request message, likely targeted at a Masternode, to retrieve a list of BlockMetadata
    instances. It specifies one field, the requester's current block hash, and expects a list of descendant blocks
    in the BlockMetadataReply.
    """
    def validate(self):
        validate_hex(self.current_block_hash, length=64, field_name="Current Block Hash")

    @classmethod
    def _deserialize_data(cls, data: bytes):
        return blockdata_capnp.BlockMetaDataRequest.from_bytes_packed(data)

    @classmethod
    def create(cls, current_block_hash):
        struct = blockdata_capnp.BlockMetaDataRequest.new_message()
        struct.currentBlockHash = current_block_hash

        return cls.from_data(struct)

    @property
    def current_block_hash(self):
        return self._data.currentBlockHash.decode()


class BlockMetaDataReply(MessageBase):
    """
    The counterpart to BlockMetaDataRequest, this message contains a list of BlockMetaData that are descendants to the
    requested block hash.
    """

    def validate(self):
        self.block_metas  # this will throw an error if any of the BlockMetaData's cannot be deserialized

    @classmethod
    def _deserialize_data(cls, data: bytes):
        return blockdata_capnp.BlockMetaDataReply.from_bytes_packed(data)

    @classmethod
    def create(cls, block_metas: List[BlockMetaData] or None):
        """
        Creates a BlockMetaDataReply instance from a list of BlockMetaData objects. If block_metas is empty/None,
        then this indicates that there are no additional blocks to request.
        # TODO docstring
        :param block_metas:
        :return:
        """
        for b in block_metas:
            assert isinstance(b, BlockMetaData), "create must be called with a list of BlockMetaData instances, but " \
                                                 "found an inconsistent element {} in block_metas arg".format(b)
        struct = blockdata_capnp.BlockMetaDataReply.new_message()

        if block_metas:
            metas_list = struct.blocks.init('data', len(block_metas))
            for i, block_meta in enumerate(block_metas):
                metas_list[i] = block_meta._data
        else:
            struct.blocks.isLatest = None

        return cls.from_data(struct)

    @lazy_property
    def block_metas(self) -> List[BlockMetaData] or None:
        """
        # TODO docstring
        :return:
        """
        if self._data.blocks.which() == 'isLatest':
            return None
        else:
            return [BlockMetaData.from_data(block_meta) for block_meta in self._data.blocks.data]
