import hashlib
from enum import Enum
from cilantro.messages import MessageBase
"""
Utility class for hashing things
"""


class HashAlgorithm(Enum):
    MD5 = 'md5'
    SHA3_256 = 'sha3_256'
    SHA1 = 'sha1'
    RIPE = 'ripemd160'


class Hasher:
    MD5 = 'md5'
    @staticmethod
    def hash(data, algorithm=HashAlgorithm.MD5, return_bytes=False) -> bytes or str:
        """
        Automatically cast the data to bytes, and hash that thang
        :param data: The data to be hashes. This method will do its best to infer its type and cast it to bytes, but
        to be sure it will work you can pass in bytes explicity
        :param return_bytes: If true, returns the hash as bytes. Otherwise, returns a hex string
        :return: A string containing the hex digest of the resulting hash. If return_bytes is True, then this hex string
        is returned in binary format
        """
        t = type(data)
        if t is str:
            data = data.encode()
        elif t is int:
            data = bytes(data)
        elif issubclass(t, MessageBase):
            data = data.serialize()

        assert type(data) is bytes, "Unable to cast data of original type {} into bytes".format(t)

        h = hashlib.new(algorithm)
        h.update(data)
        binary = h.digest()

        if return_bytes:
            return binary
        else:
            return binary.hex()

    def hash_iterable(self, iterable, algorithm=HashAlgorithm.MD5, return_bytes=False):
        data = [Hasher.hash(i, algorithm=algorithm, return_bytes=True) for i in iterable]
        # TODO -- update a hasher with all that shit
        # TODO digest and return that shit
