from cilantro.serialization import Serializer
import msgpack
import zmq

'''
    JSONSerializer
    Takes bytes on the wire and transforms them into JSON objects to send through ZMQ
    Not for production, but good for testing.
'''
class MessagePackSerializer(Serializer):
    #TODO
    pass