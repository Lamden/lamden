from cilantro_ee.messages.base.base import MessageBase
from cilantro_ee.utils import lazy_property, Hasher, set_lazy_property
from cilantro_ee.messages.utils import validate_hex
from cilantro_ee.logger import get_logger
from cilantro_ee.messages.consensus.merkle_signature import MerkleSignature
from cilantro_ee.messages.transaction.data import TransactionData
from typing import List


import capnp
import subblock_capnp

log = get_logger(__name__)


class SubBlock(MessageBase):
    def validate(self):
        #validate_hex(self.merkle_root, length=64, field_name='merkle_root')
        #validate_hex(self.input_hash, length=64, field_name='input_hash')
        assert self._data.signatures
        assert type(self._data.subBlockIdx) == int

        # If this SB contains transactions, make sure they are the same length as merkle leaves
        if len(self.transactions) > 0:
            assert len(self.transactions) == len(
                self.merkle_leaves), "Length of transactions transactions {} does not match length of merkle leaves {}".format(
                len(self.transactions), len(self.merkle_leaves))

        # TODO validate signatures, validate merkle tree

    @classmethod
    def _deserialize_data(cls, data: bytes):
        return subblock_capnp.SubBlock.from_bytes_packed(data)

    @classmethod
    def create(cls, merkle_root: str, signatures, merkle_leaves: List[str], sub_block_idx: int,
               input_hash: str, transactions: List[TransactionData]=None):
        # Validate input (for dev)
        for t in transactions:
            assert isinstance(t, TransactionData), "'transactions' must be a list of TransactionData instances, not {}".format(t)

        struct = subblock_capnp.SubBlock.new_message()
        struct.signatures = signatures
        struct.merkleLeaves = merkle_leaves
        struct.merkleRoot = merkle_root
        struct.subBlockIdx = sub_block_idx
        struct.inputHash = input_hash
        struct.transactions = [tx._data for tx in transactions]

        return cls.from_data(struct)

    def remove_tx_data(self):
        """
        Removes all transaction data (merkle leaves and transactions) from this SubBlock. Used when we want convey
        metadata over the wire, but are not interested in the actual transactions (ie. for NewBlockNotifications)
        """
        # Cast to a StructBuilder if needed so we can modify fields
        if type(self._data) is capnp.lib.capnp._DynamicStructReader:
            self._data = self._data.as_builder()

        self._data.transactions = []
        self._data.merkleLeaves = []
        set_lazy_property(self, 'transactions', [])
        set_lazy_property(self, 'merkle_leaves', [])

    @lazy_property
    def signatures(self) -> List[MerkleSignature]:
        return [MerkleSignature.from_bytes(sig) for sig in self._data.signatures]

    @lazy_property
    def merkle_leaves(self) -> List[str]:
        return [leaf for leaf in self._data.merkleLeaves]

    @property
    def merkle_root(self) -> str:
        return self._data.merkleRoot

    @property
    def is_empty(self) -> bool:
        return len(self.merkle_leaves) == 0

    @property
    def input_hash(self) -> str:
        return self._data.inputHash

    @property
    def index(self) -> int:
        return int(self._data.subBlockIdx)

    @lazy_property
    def transactions(self) -> List[TransactionData]:
        return [TransactionData.from_data(tx) for tx in self._data.transactions]


class SubBlockBuilder:

    @staticmethod
    def create(transactions: List[TransactionData]=None, num_txs=8, input_hash='A'*64, idx=0, signing_keys: List[str]=None):
        from cilantro_ee.messages.transaction.data import TransactionDataBuilder
        from cilantro_ee.protocol.structures.merkle_tree import MerkleTree

        if not transactions:
            transactions = []
            for _ in range(num_txs):
                transactions.append(TransactionDataBuilder.create_random_tx())
        transactions_bin = [tx.serialize() for tx in transactions]

        tree = MerkleTree.from_raw_transactions(transactions_bin)
        merkle_root = tree.root_as_hex

        signing_keys = signing_keys or ['AB' * 32, 'BC' * 32]
        sigs = [MerkleSignature.create_from_payload(sk, tree.root) for sk in signing_keys]

        sb = SubBlock.create(merkle_root=merkle_root, signatures=sigs, merkle_leaves=tree.leaves_as_hex,
                             sub_block_idx=idx, input_hash=input_hash, transactions=transactions)
        return sb
