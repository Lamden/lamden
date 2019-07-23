from cilantro_ee.messages.base.base import MessageBase
from cilantro_ee.utils import lazy_property, set_lazy_property, is_valid_hex
from cilantro_ee.messages.consensus.merkle_signature import MerkleSignature, build_test_merkle_sig
from cilantro_ee.protocol.structures.merkle_tree import MerkleTree
from cilantro_ee.protocol import wallet
from cilantro_ee.messages.transaction.data import TransactionData, TransactionDataBuilder
from cilantro_ee.storage.vkbook import PhoneBook
from cilantro_ee.utils.hasher import Hasher
from typing import List

import capnp
import subblock_capnp


class SubBlockContender(MessageBase):
    # TODO switch underlying data struct for this guy to Capnp (or at least JSON)
    """
    SubBlockContender is the message object that is published to master nodes (and other delegates - may be this is not needed)
    when a valid sub-block is produced at a delegate.
    It contains a list of Merkle leaves (the hashes of the transactions in the block) along with input hash, result hash,
    signagure of the delegate and some raw transactions
    """

    def validate(self):
        # self.transactions # Will throw an error if it cannot be deserialized
        # assert self.signature.sender in PhoneBook.delegates, 'Not a valid delegate'
        # assert self.signature.verify(bytes.fromhex(self.result_hash)), 'Cannot verify signature'
        # assert self._data.resultHash, "result hash field missing from data {}".format(self._data)
        # assert self._data.inputHash, "input hash field missing from data {}".format(self._data)
        # assert self._data.signature, "Signature field missing from data {}".format(self._data)
        # assert self._data.prevBlockHash, "prevBlockHash field missing from data {}".format(self._data)
        # assert hasattr(self._data, 'subBlockIdx'), "Sub-block index field missing from data {}".format(self._data)
        # assert is_valid_hex(self.result_hash, length=64), "Invalid sub-block result hash {} .. " \
        #                                                   "expected 64 char hex string".format(self.result_hash)
        # assert is_valid_hex(self.input_hash, length=64), "Invalid input sub-block hash {} .. " \
        #                                                  "expected 64 char hex string".format(self.input_hash)
        # assert is_valid_hex(self.prev_block_hash, length=64), "Invalid prev block hash {} .. " \
        #                                                       "expected 64 char hex string".format(self.prev_block_hash)
        #
        # # Ensure merkle leaves are valid hex - this may not be present in all cases
        # for leaf in self.merkle_leaves:
        #     assert is_valid_hex(leaf, length=64), "Invalid Merkle leaf {} ... expected 64 char hex string".format(leaf)
        pass

    @classmethod
    def create(cls, result_hash: bytes, input_hash: bytes, merkle_leaves: List[bytes], signature: bytes,
               transactions: List[TransactionData], sub_block_index: int, prev_block_hash: bytes):
        """
        Delegages create a _new sub-block contender and propose to master nodes
        :param result_hash: The hash of the root of this sub-block
        :param input_hash: The hash of input bag containing raw txns in order
        :param merkle_leaves: A list merkle leaves contained within this proposed block. Each leaf is a byte string
        :param signature: MerkleSignature of the delegate proposing this sub-block
        :param transactions: Partial set of raw transactions with the result state included.
        :return: A SubBlockContender object
        """


        struct = subblock_capnp.SubBlockContender.new_message()
        struct.init('merkleLeaves', len(merkle_leaves))
        struct.init('transactions', len(transactions))
        struct.resultHash = result_hash
        struct.inputHash = input_hash
        struct.merkleLeaves = merkle_leaves
        struct.signature = signature
        struct.transactions = transactions
        struct.subBlockIdx = sub_block_index
        struct.prevBlockHash = prev_block_hash

        return cls.from_data(struct)

    @classmethod
    def create_empty_sublock(cls, input_hash: bytes, signature: bytes, sub_block_index: int, prev_block_hash: bytes):
        return cls.create(result_hash=input_hash,
                          input_hash=input_hash,
                          signature=signature,
                          sub_block_index=sub_block_index,
                          merkle_leaves=[],
                          transactions=[],
                          prev_block_hash=prev_block_hash)

    @classmethod
    def _chunks(cls, l, n=64):
        for i in range(0, len(l), n):
            yield l[i:i + n]

    @classmethod
    def _deserialize_data(cls, data: bytes):
        return subblock_capnp.SubBlockContender.from_bytes_packed(data)

    # NOTE -- result_hash is the same as the merkle root
    @lazy_property
    def result_hash(self):
        return self._data.resultHash

    @lazy_property
    def input_hash(self):
        return self._data.inputHash

    @property
    def sb_index(self) -> int:
        return self._data.subBlockIdx

    @property
    def prev_block_hash(self) -> bytes:
        return self._data.prevBlockHash

    @lazy_property
    def signature(self) -> bytes:
        """
        MerkleSignature of the delegate that proposed this sub-block
        """
        # Deserialize signatures
        return self._data.signature

    @property
    def is_empty(self) -> bool:
        return len(self.merkle_leaves) == 0

    @property
    def merkle_leaves(self) -> List[str]:
        """
        The Merkle Tree leaves associated with the block (a binary tree stored implicitly as a list).
        Each element is hex string representing a node's hash.
        """
        return [leaf.hex() for leaf in self._data.merkleLeaves]

    @property
    def transactions(self) -> List[TransactionData]:
        return [TransactionData.from_bytes(tx) for tx in self._data.transactions]

    def __eq__(self, other):
        assert isinstance(other, SubBlockContender), "Attempted to compare a BlockBuilder with a non-BlockBuilder"
        return self.input_hash == other.input_hash and \
            self.result_hash == other.result_hash

    # def __repr__(self):
    #     return "SubBlockContender(sb_index={}, sender={}, prev_block_hash={}, input_hash={}, result_hash={}, " \
    #            " num_leaves={})".format(self.sb_index, self.signature.sender, self.prev_block_hash, self.input_hash,
    #                                     self.result_hash, len(self.transactions))

    def __hash__(self):
        return int(Hasher.hash(self), 16)


class SubBlockContenderBuilder:

    from cilantro_ee.constants.testnet import TESTNET_DELEGATES
    DEL_SK = TESTNET_DELEGATES[0]['sk'] if len(TESTNET_DELEGATES) > 0 else 'A' * 64
    DEL_VK = TESTNET_DELEGATES[0]['vk'] if len(TESTNET_DELEGATES) > 0 else wallet.get_vk('A' * 64)

    @classmethod
    def create(cls, transactions: List[TransactionData] = None, tx_count=5, input_hash='A' * 64, sb_index=0,
               del_sk=DEL_SK, prev_block_hash='0' * 64):
        if not transactions:
            transactions = [TransactionDataBuilder.create_random_tx() for _ in range(tx_count)]
        raw_txs = [tx.serialize() for tx in transactions]
        tree = MerkleTree.from_raw_transactions(raw_txs)
        signature = build_test_merkle_sig(msg=tree.root, sk=del_sk, vk=wallet.get_vk(del_sk))
        sbc = SubBlockContender.create(result_hash=tree.root_as_hex, input_hash=input_hash, merkle_leaves=tree.leaves,
                                       signature=signature, transactions=transactions, sub_block_index=sb_index,
                                       prev_block_hash=prev_block_hash)
        return sbc
