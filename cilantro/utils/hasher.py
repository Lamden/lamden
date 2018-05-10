"""
Utility class for hashing thangs
"""

import hashlib


class Hasher:
    """
    Just an enum of hashing algs (print property hashlib.algorithms_available for full list)
    """
    class Alg:
        MD5 = 'md5'
        SHA3_256 = 'sha3_256'
        SHA1 = 'sha1'
        RIPE = 'ripemd160'

    class Test:
        SOME_PROP = 1

    @staticmethod
    def _cast_to_bytes(data) -> bytes:
        """
        Attempts to auto-cast the data to bytes, raising an error if not possible
        :param data: The data to attempt to cast to bytes
        :return: Bytes
        :raises: An assertion if data is a non-trivial type that could not be casted to bytes
        """
        # MessageBase imported here to fix cyclic imports...TODO -- find a better solution for this
        from cilantro.messages import MessageBase

        t = type(data)

        if t is str:
            data = data.encode()
        elif t is int:
            data = bytes(data)
        elif issubclass(t, MessageBase):
            data = data.serialize()

        assert type(data) is bytes, "Unable to cast data of original type {} into bytes".format(t)

        return data

    @staticmethod
    def _read_hasher(hasher, return_bytes=False):
        binary = hasher.digest()
        if return_bytes:
            return binary
        else:
            return binary.hex()

    @staticmethod
    def hash(data, algorithm=Alg.MD5, return_bytes=False) -> bytes or str:
        """
        Attempts to automatically cast the data to bytes, and hash it. If data is an iterable, the
        elements will be iterated, serialized, and hashed.
        :param data: The data to be hashes. This method will do its best to infer its type and cast it to bytes, but
        to be sure it will work you can pass in bytes explicity
        :param algorithm: The algorithm to use (a property of Hasher.Alg
        :param return_bytes: If true, returns the hash as bytes. Otherwise, returns a hex string
        :return: A string containing the hex digest of the resulting hash. If return_bytes is True, then this hex string
        is returned in binary format
        """
        data = Hasher._cast_to_bytes(data)

        h = hashlib.new(algorithm)
        h.update(data)

        return Hasher._read_hasher(h, return_bytes=return_bytes)

    @staticmethod
    def hash_iterable(iterable, algorithm=Alg.SHA3_256, return_bytes=False) -> bytes or str:
        """
        Hashes an iterable by casting all its elements to bytes (if necessary), concatenating them, and then hashing
        the resulting binary
        :param iterable: An iterable to hash. Elements can be homo/heterogeneous.
        :param algorithm: The algorithm to use (a property of Hasher.Alg
        :param return_bytes: If true, the hash will be returned as bytes. Otherwise, a hex string will be returned
        :return: The resulting hash in bytes or as a str
        """
        hasher = hashlib.new(algorithm)

        # Hash individual datums and add to hasher
        for i in iterable:
            data = Hasher._cast_to_bytes(i)
            hasher.update(Hasher.hash(data, algorithm=algorithm, return_bytes=True))

        return Hasher._read_hasher(hasher, return_bytes=return_bytes)

