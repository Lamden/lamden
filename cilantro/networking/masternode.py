from flask import Flask
from flask_restful import Resource, Api

import zmq

app = Flask(__name__)
api = Api(app)

class Transactions(Resource):
    def post(self):
        return {'hello': 'world'}

api.add_resource(Transactions, '/')

if __name__ == '__main__':
    app.run(debug=True)