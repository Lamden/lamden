import requests
from cilantro_ee.crypto.wallet import Wallet
from cilantro_ee.crypto.transaction import TransactionBuilder


SERVER = 'http://138.197.218.53:18080'
foundation = Wallet(seed=bytes.fromhex('882b47fed47888a255bf893b384f4444b1dcc69c5ebe953c49bb5b00c5ad44eb'))


def submit_transaction(tx, server=SERVER):
    print('submitting')
    return requests.post(server, data=tx, verify=True)


def send_tx(sender, contract, function, kwargs={}):
    nonce_req = requests.get('{}/nonce/{}'.format(SERVER, sender.verifying_key().hex()))
    nonce = nonce_req.json()['nonce']
    processor = bytes.fromhex(nonce_req.json()['processor'])
    tx = TransactionBuilder(sender.verifying_key(),
                            contract=contract,
                            function=function,
                            kwargs=kwargs,
                            stamps=100_000,
                            processor=processor,
                            nonce=nonce)
    tx.sign(sender.signing_key())
    packed_tx = tx.serialize()
    res = submit_transaction(packed_tx)
    print(res.text)


def get_funds_mn():
    send_tx(foundation, 'currency', 'transfer',
            {
                'amount': 1_000_000,
                'to': 'fdf894712ada735174fbb69df7b346e30ef51d556874d73ed4ebd89c754a5060'
            })

    # send_tx(foundation, 'currency', 'transfer',
    #         {
    #             'amount': 1_000_000,
    #             'to': '47f08f716860f8c25b326133035c79f4274d80651803bc352d762b23bca7bd28'
    #         })

    return True


def get_funds_dl():
    send_tx(foundation, 'currency', 'transfer',
            {
                'amount': 1_000_000,
                'to': '933bab5ae69690b67b3124cb92b3cb6304017c7839f1ab7ad5b6325ccd59d8f7'
            })

    # send_tx(foundation, 'currency', 'transfer',
    #         {
    #             'amount': 1_000_000,
    #             'to': 'a77a0ee30deb4e51b62f3a7af9ac1456fb7c6a31891cc9455fecf55c67438b5b'
    #         })

    return True


def main():
    res_m = get_funds_mn()
    res_d = get_funds_dl()


if __name__ == "__main__":
    main()