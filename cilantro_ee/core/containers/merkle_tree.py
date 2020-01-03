from cilantro_ee.utils import Hasher, lazy_property
from typing import List
import hashlib


def merklize(leaves):
    # Make space for the parent hashes
    nodes = [None for _ in range(len(leaves) - 1)]

    # Hash all leaves so that all data is same length
    for l in leaves:
        h = hashlib.sha3_256()
        h.update(l)
        nodes.append(h.digest())

    # Hash each pair of leaves together and set the hash to their parent in the list
    for i in range((len(leaves) * 2) - 1 - len(leaves), 0, -1):
        h = hashlib.sha3_256()
        h.update(nodes[2 * i - 1] + nodes[2 * i])
        true_i = i - 1
        nodes[true_i] = h.digest()

    # Return the list
    return nodes

class MerkleTree:
    """
    Data structure for computing a merkle tree
    """
    HASH_ALG = Hasher.Alg.SHA3_256

    def __init__(self, leaves: List[bytes], hash_leaves=True):
        """
        WARNING -- It is recommended that you do not init this class directly using MerkleTree(leaves),
        but rather use one of the Factory methods below (ie from_raw_transactions, from_raw_leaves, from_hex_leaves, ..)

        Creates a merkle tree from a list of leaves. If hash_leaves is False, then it is assumed that the leaves being
        passed in are the actual leaves of the Merkle tree. Otherwise, the list of leaves will be hashed, and then this
        transformed list is used as the leaves

        :param leaves: A list of leaves to use in a Merkle tree. List elements must be any type hashable by the Hasher
        module, such as bytes, str, int, ect.
        :param hash_leaves: If True, each element of leaves will be hashed and these resulting hashes are used as the
        leaves in the construction of the MerkleTree
        """
        self.raw_leaves = leaves if hash_leaves else None

        self.nodes = MerkleTree.merklize(leaves, hash_leaves=hash_leaves)

        self.leaves = self.nodes[-len(leaves):]
        self.root = self.nodes[0]

    @classmethod
    def from_raw_transactions(cls, raw_transactions: List[bytes]):
        """
        Creates a MerkleTree from a list of raw transactions. The raw_transactions are hashed into the leaves.
        :param raw_transactions: A list of bytes. These are hashed and then used as the 'real' leaves in the MerkleTree
        :return: A MerkleTree object
        """
        return cls(leaves=raw_transactions, hash_leaves=True)

    @classmethod
    def from_raw_leaves(cls, leaves: List[bytes]):
        """
        Creates a MerkleTree from a list of 'real' Merkle leaves in byte format (transaction hashes, as bytes).
        :param leaves: A list of bytes, representing the leaves of the MerkleTree
        :return: A MerkleTree object
        """
        return cls(leaves=leaves, hash_leaves=False)

    @classmethod
    def from_hex_leaves(cls, leaves: List[str]):
        """
        Creates a MerkleTree from a list of 'real' Merkle leaves in hex string format (transaction hashes, as hex str)
        :param leaves: A list of leaves to use for the MerkleTree
        :return: A MerkleTree object
        """
        leaves = [bytes.fromhex(leaf) for leaf in leaves]
        return cls(leaves=leaves, hash_leaves=False)

    @classmethod
    def from_leaves_hex_str(cls, hex_str: str) -> 'MerkleTree':
        """
        Creates a Merkle tree from a hex string of concatenated Merkle leaves
        :param hex_str: A giant hex string representing the concatenated merkle leaves
        (ie. the return value of .leaves_as_concat_hex_str)
        :return: A MerkleTree object
        """
        assert len(hex_str) % 64 == 0, "Expected the concatenated hex_str to be divisble by 64! (Got {})".format(hex_str)
        assert len(hex_str) >= 64, "hex_str must be at least 64 characters"

        leaves = [bytes.fromhex(hex_str[i:i+64]) for i in range(0, len(hex_str), 64)]
        obj = cls(leaves, hash_leaves=False)

        return obj

    @lazy_property
    def leaves_as_hex(self) -> List[str]:
        """
        Returns the leaves of the merkle tree, each leaf represented as a hex string
        :return: A list of hex strings
        """
        return [leaf.hex() for leaf in self.leaves]

    @lazy_property
    def leaves_as_concat_hex_str(self) -> str:
        """
        Returns the leaves of the merkle tree, concatenated together into one hex string. To get the individual leaves
        from this, one must split the string every 64 characters
        :return: A long hex string representing the concatenated Merkle leaves.
        """
        hex_str = ''.join(self.leaves_as_hex)
        assert len(hex_str) % 64 == 0, "Expected leaves_as_hex_str to be divisible by 64! List of leaves is not " \
                                       "valid hex: {}".format(self.leaves_as_hex)
        return hex_str

    @lazy_property
    def root_as_hex(self) -> str:
        """
        Returns the root of the tree, represented as a hex string
        :return: A hex string representing the value of the root node of the Merkle tree
        """
        return self.root.hex()

    def parent(self, i=0) -> bytes:
        """
        Returns the parent of a particular node at index i.
        :param i: The index of the node to retrieve a parent from. Assumed to be 0 indexed
        :return: The parent of the node at index i, as bytes
        """
        if i == 0:
            return self.nodes[0]
        return self.nodes[((i + 1) // 2) - 1]

    def children(self, i) -> List[bytes]:
        """
        Retreives the children of a particular node at index i.
        :param i:  The index of the node to retrieve its children. Assumed to be 0 indexed.
        :return: The children for the node at index i, represented as a list of 2 elements; left child and right child.
         Each child is a bytes object.
        """
        return [
            self.nodes[((i + 1) * 2) - 1],
            self.nodes[(((i + 1) * 2) + 1) - 1]
        ]

    def data_for_hash(self, h: str) -> bytes:
        """
        Returns the raw data associated with a merkle leaf
        :param h: The hash of the merkle leaf. Must be 64 character valid hex
        :return: The datum which was hashed into merkle leaf with hex string 'h'
        """
        assert self.raw_leaves, "This MerkleTree was not created from raw transactions, thus it can't lookup data"
        assert h in self.leaves_as_hex, "Hash {} not found in merkle leaves".format(h)

        return self.raw_leaves[self.leaves_as_hex.index(h)]

    @staticmethod
    def verify_tree_from_bytes(leaves: List[bytes], root: bytes, hash_leaves=False) -> bool:
        """
        Attempts to verify merkle tree by building a Merkle tree from the list of leaves, and then comparing the root
        of that resulting tree to the root passed into this function
        :param leaves: The leaves of the merkle tree. List of bytes
        :param root: The alleged root of the merkle tree formed by 'leaves' arg. Must be bytes
        :return: True if the tree is valid; False otherwise
        """
        nodes = MerkleTree.merklize(leaves, hash_leaves=hash_leaves)
        return nodes[0] == root

    @staticmethod
    def verify_tree_from_str(leaves: List[str], root: str):
        """
        Attempts to verify the Merkle tree from a list of hex strings representing the merkle leaves (which are expected
        to be hashed already)
        :param leaves: A list of hex strings, 64 chars each
        :param root: The root hash, a 64 char hex str
        :return: True if the tree is valid; False otherwise
        """
        tree = MerkleTree.from_hex_leaves(leaves)
        return tree.root_as_hex == root

    @staticmethod
    def verify_tree_from_concat_str(leaves: str, root: str) -> bool:
        """
        Attempts to verify the Merkle tree from a concatenated hex string represeting the leaves.
        :param leaves: A concatenated hex string represeting the leaves (ie return value of .leaves_as_concat_hex_str)
        :param root: The expected root of the Merkle tree, represented as a hex string
        :return: True if the tree is valid; False otherwise
        """
        tree = MerkleTree.from_leaves_hex_str(leaves)
        return tree.root_as_hex == root

    @staticmethod
    def merklize(leaves: list, hash_leaves=True) -> list:
        """
        Builds a merkle tree from leaves and returns the tree as a list (representing an implicitly stored binary tree)
        :param leaves: The leaves to form a merkle tree from.
        :param hash_leaves: True if the leaves should be hashed before building the tree.
        :return: A list, which serves as an implicit representation of the merkle tree
        """
        if hash_leaves:
            leaves = [MerkleTree.hash(l) for l in leaves]

        nodes = [None for _ in range(len(leaves) - 1)]
        nodes.extend(leaves)

        for i in range((len(leaves) * 2) - 1 - len(leaves), 0, -1):
            true_i = i - 1
            nodes[true_i] = MerkleTree.hash(nodes[2 * i - 1] + nodes[2 * i])

        return nodes

    @staticmethod
    def hash(o):
        # If 'o' is a str, it is assumed to be a hex string, thus we cast it to bytes using bytes.fromhex(...)
        # instead of the default str.encode(..) that the Hasher module uses
        if type(o) is str:
            o = bytes.fromhex(o)

        return Hasher.hash(o, algorithm=MerkleTree.HASH_ALG, return_bytes=True)

    @staticmethod
    def hash_nodes(nodes: list):
        return Hasher.hash_iterable(nodes, algorithm=Hasher.Alg.SHA3_256, return_bytes=True)
