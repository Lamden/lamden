from flask import Flask
from flask_restful import Resource, Api

import zmq

app = Flask(__name__)
api = Api(app)

context = zmq.Context()
publisher = context.socket(zmq.PUB)

class Transactions(Resource):
    def post(self):
        # serialize this bad boy

        # send the message over zmq
        try:
            publisher.bind('tcp://127.0.0.1:9999')
            publisher.send(b'test_message')
        except:
            return {'error' : 'response'}
        finally:
            publisher.unbind()

        return {'hello': 'world'}

api.add_resource(Transactions, '/')

if __name__ == '__main__':
    app.run(debug=True)