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
    def serialize(d: dict):
        """
        Convert dict -> bytes
        :param d: dict
        :return: bytes
        """
        try:
            return str.encode(json.dumps(d))
        except Exception as e:
            print(e)
            return {'error status': e}

    @staticmethod
    def deserialize(b: bytes):
        """
        bytes -> dict
        :param d:
        :return:
        """
        try:
            return json.loads(b.decode())
        except Exception as e:
            print(e)
            return{'error status': e}