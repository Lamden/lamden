from cilantro.serialization import Serializer
import json
import zmq

class JSONSerializer(Serializer):
    @staticmethod
    def serialize(b: bytes):
        try:
            return json.dumps(b.decode())
        except Exception as e:
            print(e)
            return 0

    @staticmethod
    def deserialize(s: bytes):
        return json.loads(s)

    @staticmethod
    def send(d, p: zmq.Context):
        p.send_json(d.decode("utf-8"))
