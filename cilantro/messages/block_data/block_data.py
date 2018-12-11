from cilantro.messages.base.base import MessageBase
from cilantro.messages.transaction.data import TransactionData, TransactionDataBuilder
from cilantro.utils import lazy_property, Hasher
from cilantro.protocol.structures.merkle_tree import MerkleTree
from cilantro.constants.testnet import TESTNET_MASTERNODES, TESTNET_DELEGATES
from cilantro.messages.block_data.sub_block import SubBlock
from cilantro.messages.utils import validate_hex
from typing import List
from cilantro.logger import get_logger
from cilantro.storage.vkbook import VKBook

import blockdata_capnp

log = get_logger(__name__)
GENESIS_BLOCK_HASH = '0' * 64  # TODO find a better home for this?


class BlockData(MessageBase):

    # TODO find this method a better home. Maybe in utils or something?
    @staticmethod
    def compute_block_hash(sbc_roots: List[str], prev_block_hash: str):
        return Hasher.hash_iterable(sbc_roots + [prev_block_hash])

    def validate(self):
        # TODO clean this up, and share subclass with BlockMetaData. Then we can do deep validation in one place
        assert validate_hex(self.block_hash, 64), 'Invalid block hash {}'.format(self.block_hash)
        assert validate_hex(self._data.prevBlockHash, 64), 'Invalid previous block hash'
        assert self.block_num >= 0, "Block num must be greater than or equal to 0"

        # Validate block hash
        expected_b_hash = BlockData.compute_block_hash(sbc_roots=self.merkle_roots, prev_block_hash=self.prev_block_hash)
        assert expected_b_hash == self.block_hash, "Block hash could not be verified (does not match computed hash)"

        # Validate sub_block order
        for i, sb in enumerate(self.sub_blocks):
            assert sb.index == i, "Sub blocks out of order!"

    @classmethod
    def _deserialize_data(cls, data):
        return blockdata_capnp.BlockData.from_bytes_packed(data)

    @classmethod
    def create(cls, block_hash: str, prev_block_hash: str, block_owners: List[str], block_num: int,
               sub_blocks: List[SubBlock]):

        struct = blockdata_capnp.BlockData.new_message()
        struct.blockHash = block_hash
        struct.blockNum = block_num
        struct.prevBlockHash = prev_block_hash
        struct.blockOwners = block_owners

        # Sort sub-blocks by index if they are not done so already
        sub_blocks = sorted(sub_blocks, key=lambda sb: sb.index)
        struct.subBlocks = [sb._data for sb in sub_blocks]

        return cls.from_data(struct)

    @lazy_property
    def block_hash(self) -> str:
        return self._data.blockHash

    @property
    def block_num(self) -> int:
        return self._data.blockNum

    @lazy_property
    def prev_block_hash(self) -> str:
        return self._data.prevBlockHash

    @lazy_property
    def sub_blocks(self) -> List[SubBlock]:
        return [SubBlock.from_data(sb) for sb in self._data.subBlocks]

    @lazy_property
    def merkle_leaves(self) -> List[str]:
        leaves = []
        for sb in self.sub_blocks:
            leaves += sb.merkle_leaves
        return leaves

    @lazy_property
    def transactions(self) -> List[TransactionData]:
        txs = []
        for sb in self.sub_blocks:
            txs += sb.transactions
        return txs

    # TODO -- make it list instead of dir
    @lazy_property
    def indexed_transactions(self) -> dict:
        return {
            TransactionData.from_bytes(tx).hash: tx for tx in self.transactions
        }

    @lazy_property
    def block_owners(self) -> List[str]:
        return [x for x in self._data.blockOwners]  # Necessary to cast capnp list builder to Python list

    @lazy_property
    def merkle_roots(self) -> List[str]:
        return [sb.merkle_root for sb in self.sub_blocks]

    @lazy_property
    def input_hashes(self) -> List[str]:
        return [sb.input_hash for sb in self.sub_blocks]


class GenesisBlockData(BlockData):

    def validate(self):
        pass  # no validation for genesis block hash

    @classmethod
    def create(cls, sk, vk):
        struct = blockdata_capnp.BlockData.new_message()
        struct.blockHash = GENESIS_BLOCK_HASH
        struct.blockNum = 0
        struct.blockOwners = [vk]

        return cls.from_data(struct)


# class BlockDataBuilder:
#     MN_SK = TESTNET_MASTERNODES[0]['sk'] if len(TESTNET_MASTERNODES) > 0 else 'A' * 64
#     MN_VK = TESTNET_MASTERNODES[0]['vk'] if len(TESTNET_MASTERNODES) > 0 else 'A' * 64
#     DEL_SK = TESTNET_DELEGATES[0]['sk'] if len(TESTNET_DELEGATES) > 0 else 'A' * 64
#     DEL_VK = TESTNET_MASTERNODES[0]['vk'] if len(TESTNET_MASTERNODES) > 0 else 'A' * 64
#
#     @classmethod
    # def create_block(cls, blk_num=0, prev_block_hash=GENESIS_BLOCK_HASH, merkle_roots=None, all_transactions=[],
    #                  tx_count=5, sub_block_count=2, mn_sk=MN_SK, mn_vk=MN_VK, del_sk=DEL_SK, states=None):
    #     merkle_roots = []
    #     input_hashes = []
    #     create_new_transactions = len(all_transactions) == 0
    #     for i in range(sub_block_count):
    #         if create_new_transactions:
    #             transactions = []
    #             for j in range(tx_count):
    #                 state = states[(i*tx_count)+j] if states else 'SET x 1'
    #                 transactions.append(TransactionDataBuilder.create_random_tx(state=state))
    #             all_transactions += transactions
    #         else:
    #             transactions = all_transactions[i*tx_count:(i+1)*tx_count]
    #         merkle_leaves = [Hasher.hash(tx) for tx in transactions]
    #         sub_block = {
    #             'merkle_root': MerkleTree.from_hex_leaves(merkle_leaves).root_as_hex,
    #             'input_hash': Hasher.hash_iterable(transactions)
    #         }
    #         merkle_roots.append(sub_block['merkle_root'])
    #         input_hashes.append(sub_block['input_hash'])
    #
    #     block_hash = BlockData.compute_block_hash(merkle_roots, prev_block_hash)
    #     block_num = blk_num
    #     block = BlockData.create(block_hash=block_hash, prev_block_hash=prev_block_hash, transactions=all_transactions,
    #                              block_owners=[mn_vk], merkle_roots=merkle_roots, block_num=block_num,
    #                              input_hashes=input_hashes)
    #
    #     return block

