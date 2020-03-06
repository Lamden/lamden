import requests
from cilantro_ee.crypto.wallet import Wallet
from cilantro_ee.crypto.transaction import TransactionBuilder


SERVER = 'http://138.68.43.35:18080'
foundation = Wallet(seed=bytes.fromhex('882b47fed47888a255bf893b384f4444b1dcc69c5ebe953c49bb5b00c5ad44eb'))


def submit_transaction(tx, server=SERVER):
    print('submitting')
    return requests.post(server, data=tx, verify=False)


def send_tx(sender, contract, function, kwargs={}):
    nonce_req = requests.get('{}/nonce/{}'.format(SERVER, sender.verifying_key().hex()))
    nonce = nonce_req.json()['nonce']
    processor = bytes.fromhex(nonce_req.json()['processor'])
    tx = TransactionBuilder(sender.verifying_key(),
        contract=contract,
        function=function,
        kwargs=kwargs,
        stamps=500000,
        processor=processor,
        nonce=nonce)
    tx.sign(sender.signing_key())
    packed_tx = tx.serialize()
    res = submit_transaction(packed_tx)
    print(res.text)


def get_funds():
    send_tx(foundation, 'currency', 'transfer',
            {
                'amount': 1_000_000,
                'to': '0273b7051a137d1a5ee3d615cad20e8573ec2615da69c845085d6c6e45200482'
            })


get_funds()