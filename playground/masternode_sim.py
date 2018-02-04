import json
import zmq
import time

# FAKE MASTERNODE FOR TESTING PURPOSES ONLY

class JSONSerializer():
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


class Masternode(object):
    def __init__(self, host='127.0.0.1', port='4000', serializer=JSONSerializer()):
        self.host = host
        self.port = port
        self.serializer = serializer

        self.context = zmq.Context()
        self.publisher = self.context.socket(zmq.PUB)

        self.url = 'tcp://{}:{}'.format(self.host, self.port)

    def process_tranasaction(self):
        d = {'payload': {'to': 'satoshi', 'amount': '100', 'from': 'nakamoto'}, 'metadata': {'sig':'x287', 'proof': '000'}}
        self.publisher.bind(self.url)

        for i in range(100000):
            self.serializer.send(d, self.publisher)
            print('Sending message {}'.format(i))
        self.publisher.unbind(self.url)


a = Masternode()
a.process_tranasaction()