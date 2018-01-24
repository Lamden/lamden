from flask import Flask, request, jsonify
from cilantro.serialization import JSONSerializer
import zmq

class Masternode(object):
    def __init__(self, host='127.0.0.1', port='9999', serializer=JSONSerializer):
        self.host = host
        self.port = port
        self.serializer = serializer

        self.context = zmq.Context()
        self.publisher = self.context.socket(zmq.SUB)

        self.url = 'tcp://{}:{}'.format(self.host, self.port)

    def process_tranasaction(self, data=None):
        try:
            d = self.serializer.serialize(data)
        except:
            return {'status': 'Could not serialize transaction' }

        try:
            self.publisher.bind(self.url)
            self.serializer.send(d, self.publisher)
            print('ay')
        except Exception as e:
            print(e)
        finally:
            self.publisher.unbind(self.url)

        return { 'status' : '{} successfully published to the network'.format(d) }

app = Flask(__name__)

@app.route('/', methods=['POST'])
def process_transaction():
    m = Masternode()
    return jsonify(m.process_tranasaction(request.get_data()))

if __name__ == '__main__':
    app.run()