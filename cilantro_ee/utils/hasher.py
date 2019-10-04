"""
Utility class for hashing thangs
"""
import hashlib
from cilantro_ee.core.messages.capnp_impl.capnp_impl import pack, unpack


class Hasher:
    """
    Just an enum of hashing algs (print property hashlib.algorithms_available for full list)
    """
    class Alg:
        MD5 = 'md5'
        SHA3_256 = 'sha3_256'
        SHA1 = 'sha1'
        RIPE = 'sha256'
        SHAKE_128 = 'shake_128'
        SHAKE_256 = 'shake_256'

    DEFAULT_ALG = Alg.SHA3_256

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
        from cilantro_ee.utils import int_to_bytes

        assert data is not None, "Cannot hash a None type!"

        t = type(data)

        if t is str:
            data = data.encode()
        elif t is int:
            data = pack(data)

        assert type(data) is bytes, "Unable to cast data of original type {} into bytes".format(t)

        return data

    @staticmethod
    def _read_hasher(hasher, return_bytes=False, digest_len=0):
        if digest_len > 0:
            binary = hasher.digest(digest_len)
        else:
            binary = hasher.digest()

        if return_bytes:
            return binary
        else:
            return binary.hex()

    @staticmethod
    def hash(data, algorithm=DEFAULT_ALG, return_bytes=False, digest_len: int=0) -> bytes or str:
        """
        Attempts to automatically cast the data to bytes, and hash it. If digest_len is specified, shake_256 will be
        used (unless algorithm is set to shake_128) to compute a variable size digest.
        :param data: The data to be hashes. This method will do its best to infer its type and cast it to bytes, but
        to be sure it will work you can pass in bytes explicity
        :param algorithm: The algorithm to use (a property of Hasher.Alg)
        :param return_bytes: If true, returns the hash as bytes. Otherwise, returns a hex string
        :param digest_len: The optional length of the digest (as an int). Max is 256.
         If this is specified, algorithm must be either Alg.SHAKE_256 or Alg.SHAKE_128
        :return: A string containing the hex digest of the resulting hash. If return_bytes is True, then this hex string
        is returned in binary format
        """
        data = Hasher._cast_to_bytes(data)

        if digest_len > 0:
            if algorithm != Hasher.DEFAULT_ALG:
                assert algorithm in (Hasher.Alg.SHAKE_128, Hasher.Alg.SHAKE_256), \
                    "If digest_len is set, algorithm must be Alg.SHAKE_128 or Alg.SHAKE_256"
            else:
                algorithm = Hasher.Alg.SHAKE_256

            assert digest_len <= 256//8, "digest_len must be less than or equal to 32"

            if digest_len > 128//8:
                assert algorithm == Hasher.Alg.SHAKE_256, "digest_len greater than 16 must use SHAKE_256"

        h = hashlib.new(algorithm)
        h.update(data)

        return Hasher._read_hasher(h, return_bytes=return_bytes, digest_len=digest_len)

    @staticmethod
    def hash_iterable(iterable, algorithm=DEFAULT_ALG, return_bytes=False) -> bytes or str:
        """
        Hashes an iterable by casting all its elements to bytes (if necessary), concatenating them, and then hashing
        the resulting binary
        :param iterable: An iterable to hash. Elements can be homo/heterogeneous.
        :param algorithm: The algorithm to use (a property of Hasher.Alg
        :param return_bytes: If true, the hash will be returned as bytes. Otherwise, a hex string will be returned
        :return: The resulting hash in bytes or as a str
        """
        # Concatenate individual binary datums
        data = b''
        for i in iterable:
            data += Hasher._cast_to_bytes(i)

        hasher = hashlib.new(algorithm)
        hasher.update(data)

        return Hasher._read_hasher(hasher, return_bytes=return_bytes)
