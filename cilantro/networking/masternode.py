from flask import Flask, request

import zmq

app = Flask(__name__)

context = zmq.Context()
publisher = context.socket(zmq.PUB)

HOST = '127.0.0.1'
PORT = '4444'
URL = 'tcp://{}:{}'.format(HOST, PORT)

@app.route('/', methods=['POST'])
def process_transaction():

    data = request.args.get('tx')
    print(data)
    try:
        publisher.bind(URL)
        publisher.send(data)
    except Exception as e:
        print(e)
    finally:
        publisher.unbind(URL)

    return 'success'

if __name__ == '__main__':
    app.run()
