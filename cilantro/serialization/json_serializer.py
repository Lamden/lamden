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
    def serialize(b: bytes):
        try:
            return json.loads(b.decode())
        except Exception as e:
            print(e)
            return { 'error' : 'error' }

    @staticmethod
    def deserialize(d: dict):
        return json.dumps(d)

    @staticmethod
    def send(d: dict, p: zmq.Context):
        p.send_json(d)