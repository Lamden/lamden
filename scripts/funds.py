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
    #print(res.text)


def get_funds_mn():
    send_tx(foundation, 'currency', 'transfer',
            {
                'amount': 1_000_000,
                'to': '0273b7051a137d1a5ee3d615cad20e8573ec2615da69c845085d6c6e45200482'
            })
    return True


def get_funds_dl():
    send_tx(foundation, 'currency', 'transfer',
            {
                'amount': 1_000_000,
                'to': 'b6c26304d802140992bcd040538c5e9c2bc85644b620260dca838d5e91f0fdaa'
            })
    return True


def main():
    res_m = get_funds_mn()
    res_d = get_funds_dl()


if __name__ == "__main__":
    main()