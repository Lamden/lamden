import json
import hashlib
import secrets
import zmq

# FAKE WITNESS FOR TESTING PURPOSES ONLY
# port 4000

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

class SHA3POW():
    @staticmethod
    def find(o: bytes):
        while True:
            h = hashlib.sha3_256()
            s = secrets.token_bytes(16)
            h.update(o + s)
            if h.digest().hex()[0:3] != '000':
                break
        return s.hex()[2:], h.digest().hex()[2:]

    @staticmethod
    def check(o: bytes, proof: str):
        h = hashlib.sha3_256()
        s = bytes.fromhex(proof)
        h.update(o + s)
        if h.digest().hex()[0:3] != '000':
            return True
        return False

class Witness(object):
    def __init__(self, host='127.0.0.1', sub_port='4000', serializer=JSONSerializer, proof=SHA3POW):
        self.host = host
        self.sub_port = sub_port
        self.pub_port = '4488'
        self.sub_url = 'tcp://{}:{}'.format(self.host, self.sub_port)
        self.pub_url = 'tcp://{}:{}'.format(self.host, self.pub_port)

        self.serializer = serializer

        self.hasher = proof

        self.context = zmq.Context()
        self.witness_sub = self.context.socket(zmq.SUB)

        self.witness_sub.setsockopt_string(zmq.SUBSCRIBE, '')

    def accept_incoming_transactions(self):
        try:
            self.witness_sub.connect(self.sub_url)
        except Exception as e:
            return {'status': 'Could not connect to witness sub socket'}

        for i in range(1000000000):
            """Main loop entry point for witness sub"""
            tx = self.witness_sub.recv_json(flags=0, encoding='utf-8')
            if tx != -1:
                try:
                    raw_tx = self.serializer.deserialize(tx)
                except Exception as e:
                    return {'status': 'Could not deserialize transaction'}
                print(raw_tx + 'number {}'.format(i))
            else:
                print('No tx data')

            #     if self.hasher.check(raw_tx, raw_tx.payload['metadata']['proof']):
            #         self.confirmed_transaction_routine()
            #     else:
            #         return {'status': 'Could not confirm transaction POW'}
            # else:
            #     return {'status: No witness sub socket activity'}

    def activate_witness_publisher(self):
        """Routine to turn witness behavior from masternode subscriber to publisher for delegates by changing port"""
        self.witness_pub = self.context.socket(zmq.PUB)
        self.witness_pub.bind(self.pub_url)

    def confirmed_transaction_routine(self, raw_tx):
        """take approvated transaction data, serialize it, and open publisher socket.
         Then publish along tx info to delegate sub and then unbind socket"""
        tx_to_delegate = self.serializer.serialize(raw_tx)
        self.activate_witness_publisher()
        self.witness_pub.send_json(tx_to_delegate, encoding='utf-8')
        self.witness_pub.unbind(self.pub_url) # unbind socket

b = Witness()
b.accept_incoming_transactions()