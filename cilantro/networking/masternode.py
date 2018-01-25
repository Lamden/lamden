from flask import Flask, request, jsonify
from cilantro.serialization import JSONSerializer
import zmq

'''
    Masternode
    These are the entry points to the blockchain and pass messages on throughout the system. They are also the cold
    storage points for the blockchain once consumption is done by the network.
    
    They have no say as to what is 'right,' as governance is ultimately up to the network. However, they can monitor
    the behavior of nodes and tell the network who is misbehaving. 
'''

class Masternode(object):
    def __init__(self, host='127.0.0.1', port='9999', serializer=JSONSerializer):
        self.host = host
        self.port = port
        self.serializer = serializer

        self.context = zmq.Context()
        self.publisher = self.context.socket(zmq.PUB)

        self.url = 'tcp://{}:{}'.format(self.host, self.port)

    def process_tranasaction(self, data=None):
        d = None
        try:
            d = self.serializer.serialize(data)
            print(d)
        except:
            return {'status': 'Could not serialize transaction' }

        try:
            self.publisher.bind(self.url)
            self.serializer.send(d, self.publisher)
            print('ay')
        except Exception as e:
            print(e)
            return {'status': 'Could not send transaction'}
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