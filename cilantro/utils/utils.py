import hashlib
from decimal import Decimal, getcontext

class Encoder:
    @staticmethod
    def encode(o):
        if o.__class__ == str:
            return o.encode()
        elif o.__class__ == int:
            return o.to_bytes(16, byteorder='big')
        return o

    @staticmethod
    def int(b: bytes) -> int:
        if b is None:
            return 0
        return int.from_bytes(b, byteorder='big')

    @staticmethod
    def float(b: bytes) -> float:
        try:
            s = b.decode()
            i = float(s)
        except:
            if b == None:
                i = 0
        return i

    @staticmethod
    def str(b: bytes) -> str:
        s = b.decode()
        return s

    @staticmethod
    def dict(d: dict) -> dict:
        new_d = {}
        for k, v in d.items():
            new_d[k.decode()] = v.decode()
        return new_d

    @staticmethod
    def decimal(b: bytes, precision=16):
        getcontext().prec = precision
        return int(b)

    @staticmethod
    def hash_tuple(t: tuple) -> str:
        """
        Squashes the tuple into a string, and hashes it using sha3. This can be used
        used for storing transaction tuples as redis keys
        :param t: Any tuple
        :return: A hex string representing the sha3 hash of the tuple
        """
        h = hashlib.sha3_256()
        h.update(''.join((str(x) for x in t)).encode())
        return h.hexdigest()

    @staticmethod
    def str_from_tuple(t: tuple) -> str:
        """
        Generates a compact string representation of a tuple, without parenthesis or spaces between commas
        Ex) (1, 2, 'stu') -> "1,2,stu"
        :param t: A tuple
        :return: A compact string representing the tuple
        """
        return ','.join((str(x) for x in t))

    @staticmethod
    def tuple_from_str(s: str) -> tuple:
        """
        Inverse operation of str_from_tuple. Takes a compact string representing a tuple, and returns the origin tuple
        (casting numeric values back to floats)
        :param s: A compact string representing the tuple
        :return: A tuple
        """
        def attempt_convert_float(possible_float: str):
            try:
                f = float(possible_float)
                return f
            except ValueError:
                return possible_float

        return tuple([attempt_convert_float(x) for x in s.split(',')])