from cilantro.serialization import Serializer
import json
import zmq

'''
    JSONSerializer
    Takes bytes on the wire and transforms them into JSON objects to send through ZMQ
    Not for production, but good for testing.
'''


class JSONSerializer(Serializer):
    @staticmethod
    def serialize(d: dict) -> bytes:
        """
        Convert dict -> bytes
        :param d: dict
        :return: bytes
        """
        # NOTE: it is imperative to sort the keys when serializing otherwise the hashcash will very likely fail
        return json.dumps(d, sort_keys=True, separators=(',', ':')).encode()

    @staticmethod
    def deserialize(b: bytes) -> dict:
        """
        bytes -> dict
        :param b: Bytes to load as json
        :return: a dictionary
        """
        return json.loads(b.decode())