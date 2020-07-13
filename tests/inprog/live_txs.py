from cilantro_ee.crypto.wallet import Wallet
from cilantro_ee.crypto.transaction import TransactionBuilder

import requests


def submit_transaction(tx, server):
    return requests.post(server, data=tx, verify=False)


def make_tx_packed(sender, server, contract_name, function_name, kwargs={}, stamps=10_000):
    wallet = Wallet(seed=sender)

    nonce_req = requests.get('{}/nonce/{}'.format(server, wallet.verifying_key().hex()))
    nonce = nonce_req.json()['nonce']
    processor = bytes.fromhex(nonce_req.json()['processor'])

    batch = TransactionBuilder(
        sender=wallet.verifying_key,
        contract=contract_name,
        function=function_name,
        kwargs=kwargs,
        stamps=stamps,
        processor=processor,
        nonce=nonce
    )

    batch.sign(sender)
    b = batch.serialize()

    return b
