from cilantro.serialization import Serializer
import json

class JSONSerializer(Serializer):
    @staticmethod
    def serialize(d: dict):
        return json.dumps(d)

    @staticmethod
    def deserialize(s: bytes):
        return json.loads(s)