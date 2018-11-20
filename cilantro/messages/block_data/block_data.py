from cilantro.messages.base.base import MessageBase
from cilantro.messages.transaction.data import TransactionData, TransactionDataBuilder
from cilantro.messages.consensus.merkle_signature import MerkleSignature, build_test_merkle_sig
from cilantro.utils import lazy_property, Hasher, lazy_func
from cilantro.protocol.structures.merkle_tree import MerkleTree
from cilantro.messages.utils import validate_hex
from cilantro.constants.testnet import TESTNET_MASTERNODES, TESTNET_DELEGATES
from cilantro.messages.block_data.block_metadata import BlockMetaData, NewBlockNotification
from typing import List
from cilantro.logger import get_logger
from cilantro.storage.vkbook import VKBook
import time, uuid

import capnp
import blockdata_capnp

log = get_logger(__name__)

class BlockData(MessageBase):

    # TODO find this method a better home. Maybe in utils or something?
    @staticmethod
    def compute_block_hash(sbc_roots: List[str], prev_block_hash: str):
        return Hasher.hash_iterable(sbc_roots + [prev_block_hash])

    def validate(self):
        assert self._data.blockHash, 'No field "blockHash"'
        assert hasattr(self._data, 'blockNum'), 'No field "blockNum"'
        assert self._data.transactions, 'No field "transactions"'
        assert self._data.prevBlockHash, 'No field "prevBlockHash"'
        assert self._data.masternodeSignature, 'No field "masternodeSignature"'
        assert self.masternode_signature.sender in VKBook.get_masternodes(), 'Not a valid masternode'
        assert self.masternode_signature.verify(self.block_hash.encode()), 'Cannot verify signature'

    @classmethod
    def _deserialize_data(cls, data):
        return blockdata_capnp.BlockData.from_bytes_packed(data)

    @classmethod
    def create(cls, block_hash: str, prev_block_hash: str, transactions: List[TransactionData],
               masternode_signature: MerkleSignature, merkle_roots: List[str],
               input_hashes: List[str] = [], block_num: int=0):
        struct = blockdata_capnp.BlockData.new_message()
        struct.init('transactions', len(transactions))
        struct.init('merkleRoots', len(merkle_roots))
        struct.blockHash = block_hash
        struct.blockNum = block_num
        struct.inputHashes = input_hashes
        struct.merkleRoots = [mr.encode() for mr in merkle_roots]
        struct.prevBlockHash = prev_block_hash
        struct.masternodeSignature = masternode_signature.serialize()
        struct.transactions = [tx.serialize() for tx in transactions]
        return cls.from_data(struct)

    @lazy_property
    def block_hash(self) -> str:
        return self._data.blockHash.decode()

    @property
    def block_num(self) -> int:
        return int(self._data.blockNum)

    @lazy_property
    def prev_block_hash(self) -> str:
        return self._data.prevBlockHash.decode()

    @lazy_property
    def transactions(self) -> List[TransactionData]:
        return [TransactionData.from_bytes(tx) for tx in self._data.transactions]

    @lazy_property
    def masternode_signature(self) -> MerkleSignature:
        return MerkleSignature.from_bytes(self._data.masternodeSignature)

    @lazy_property
    def merkle_roots(self) -> List[str]:
        return [mr.decode() for mr in self._data.merkleRoots]

    @lazy_property
    def input_hashes(self) -> List[str]:
        return [input_hash.decode() for input_hash in self._data.inputHashes]

MN_SK = TESTNET_MASTERNODES[0]['sk']
MN_VK = TESTNET_MASTERNODES[0]['vk']
DEL_SK = TESTNET_DELEGATES[0]['sk']
DEL_VK = TESTNET_MASTERNODES[0]['vk']
PREV_BLOCK_HASH = Hasher.hash('0' * 64)

class BlockDataBuilder:
    block_num = 1
    @classmethod
    def create_block(cls, prev_block_hash=PREV_BLOCK_HASH, merkle_roots=None, all_transactions=None, tx_count=5, sub_block_count=2, mn_sk=MN_SK, mn_vk=MN_VK, del_sk=DEL_SK):
        input_hashes = [uuid.uuid4().hex * 2 for i in range(sub_block_count)]
        if not all_transactions:
            all_transactions = []
            merkle_roots = []
            input_hashes = []
            for i in range(sub_block_count):
                transactions = [TransactionDataBuilder.create_random_tx() for i in range(tx_count)]
                merkle_leaves = [Hasher.hash(tx) for tx in transactions]
                sub_block = {
                    'merkle_root': MerkleTree.from_hex_leaves(merkle_leaves).root_as_hex,
                    'transactions': transactions,
                    'input_hash': Hasher.hash_iterable(transactions)
                }
                merkle_roots.append(sub_block['merkle_root'])
                input_hashes.append(sub_block['input_hash'])
                all_transactions += transactions
        block_hash = BlockData.compute_block_hash(merkle_roots, prev_block_hash)
        block_num = cls.block_num
        signature = build_test_merkle_sig(msg=block_hash.encode(), sk=mn_sk, vk=mn_vk)
        block = BlockData.create(block_hash=block_hash, prev_block_hash=prev_block_hash, transactions=all_transactions,
                                 masternode_signature=signature, merkle_roots=merkle_roots, block_num=block_num,
                                 input_hashes=input_hashes)

        # block_dict = {'blk_num': cls.block_num,'block_hash': block_hash, 'prev_block_hash': prev_block_hash,
        #               'masternode_signature': signature}
        # block_dict['merkle_roots']=merkle_roots
        # block_dict['transactions']=transactions
        # block_dict['input_hashes']=input_hashes

        cls.block_num += 1
        return block
