from cilantro.messages import MessageBase, BlockContender
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
        self.block_contender  # Will raise exception if block_contender cannot be deserialized

        # TODO validate all 'hash' properties are valid hex of appropriate length
        # merkle_leaves shoudl be list of 64 char hex
        # masternode_signature shoudl be 128 char hex
        # ect ect
        # all properties on struct shoudl be set (no Nones!)
        pass

    def validate_block_data(self):
        """
        Attempts to validate the block data, raising an Exception if any fields are invalid.
        See BlockStorageDriver.validate_block_data for validation details.
        :return: None
        :raises: An exception if validation fails
        """
        pass
        # TODO implement
        # package all this classes properties into an appropriate dict, and reuse BlockStorageDriver.validate_block_data

        # then, compute the block hash using BlockStorageDriver.compute_block_hash raise Exception if
        # this does not equals self.block_hash (see line 377 in BlockStorageDriver._validate_block_link for example)

    @classmethod
    def _deserialize_data(cls, data: bytes):
        return blockdata_capnp.BlockMetaData.from_bytes_packed(data)

    @classmethod
    def create(cls, hash: str, merkle_root: str, merkle_leaves: List[str], prev_block_hash: str, timestamp: int,
               masternode_sig: str, masternode_vk: str, block_contender: BlockContender):
        struct = blockdata_capnp.BlockMetaData.new_message()

        # TODO set all fields on struct
        # - will have to 'init' the merkleLeaves field cause its a list, for example see BlockMetaDataReply.create

        return cls.from_data(struct)

    @property
    def block_hash(self) -> str:
        return self._data.hash.decode()

    @property
    def merkle_root(self) -> str:
        return self._data.merkleRoot.decode()

    @lazy_property
    def merkle_leaves(self) -> List[str]:
        return [leaf.decode() for leaf in self._data.merkleLeaves]

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
                metas_list[i] = block_meta.serialize()
        else:
            struct.blocks.unset = None

        return cls.from_data(struct)

    @lazy_property
    def block_metas(self) -> List[BlockMetaData] or None:
        """
        # TODO docstring
        :return:
        """
        if self._data.blocks.which() == 'unset':
            return None
        else:
            return [BlockMetaData.from_bytes(block_meta) for block_meta in self._data.blocks.data]
