from cilantro_ee.crypto.wallet import Wallet
from cilantro_ee.crypto.transaction import TransactionBuilder
import requests
requests.packages.urllib3.disable_warnings()
import secrets

SERVER = 'http://138.197.218.53:18080'

master = Wallet(seed=bytes.fromhex('8e0ca452e1a0d3b4e104accdb798b57940c1241c931861e6487c3f67a8863c4b'))
delegate = Wallet(seed=bytes.fromhex('e54ec7ca25454feed3084bfbf49c81e423805ad3f2440344abffe155c90c5463'))
delegate2 = Wallet(seed=bytes.fromhex('0e61c76732d17c3490f4dda132881866ac901393dfc23ea688d5d831afbc815e'))

foundation = Wallet(seed=bytes.fromhex('882b47fed47888a255bf893b384f4444b1dcc69c5ebe953c49bb5b00c5ad44eb'))

delegate_to_be = Wallet('e649981a350f230b5fd5c197ded3ea59374dd6f069ead715b2345da8d788eeb0')

stu = Wallet('f15b8ddbef914ee97ccecfb7377d83bb7d74bd52aaa2470e3d68caf807c818a7')

jeffie = Wallet('18b4eb5f9a269d88b51fe84859944c48d16b24f585a94e8cfb5e469def1cee25')


def submit_transaction(tx, server=SERVER):
    print('submitting')
    return requests.post(server, data=tx, verify=False)


# reciever = 'ee2e928015fd8433c8c6da7234504968a1bde751b0784c3efbe4bc42628d5e9b'
# SK = 'e54ec7ca25454feed3084bfbf49c81e423805ad3f2440344abffe155c90c5463'


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


def send_batch_1():
    # From foundation, to delegate to be, amount alot, currency tx
    send_tx(foundation, 'currency', 'transfer',
        {
            'amount': 100_000,
            'to': '270add00fc708791c97aeb5255107c770434bd2ab71c2e103fbee75e202aa15e'
        })

    # send_tx(foundation, 'currency', 'transfer',
    # 	{
    # 		'amount': 100_010,
    # 		'to': delegate.verifying_key().hex()
    # 	})

    # send_tx(foundation, 'currency', 'transfer',
    # 	{
    # 		'amount': 100_010,
    # 		'to': delegate2.verifying_key().hex()
    # 	})

    # send_tx(foundation, 'currency', 'transfer',
    # 	{
    # 		'amount': 100_010,
    # 		'to': stu.verifying_key().hex()
    # 	})


def send_batch_2():
    # Currency tx, approve, from delegate to be, from elect delegates
    send_tx(delegate_to_be, 'currency', 'approve',
        {
            'amount': 100_010,
            'to': 'elect_delegates'
        })

    # elect delegates, register as delegate, from delegate to be
    send_tx(delegate_to_be, 'elect_delegates', 'register')

    # from foundation, to stu, send currency
    send_tx(foundation, 'currency', 'transfer',
        {
            'amount': 100_010,
            'to': stu.verifying_key().hex()
        })

    # currency, approve, from stu, to elect delegates
    send_tx(stu, 'currency', 'approve',
        {
            'amount': 100_010,
            'to': 'elect_delegates'
        })

    # elect delegates, vote for delegate to be, from stu
    send_tx(stu, 'elect_delegates', 'vote_candidate',
        {
            'address': delegate_to_be.verifying_key().hex()
        })


def send_batch_3():
    # delegates create motion
    send_tx(delegate, 'election_house', 'vote',
        {
            'policy': 'delegates',
            'value': ['introduce_motion', 2]
        })

    # delegates vote on motion
    send_tx(delegate, 'election_house', 'vote',
        {
            'policy': 'delegates',
            'value': ['vote_on_motion', True]
        })

    send_tx(delegate2, 'election_house', 'vote',
        {
            'policy': 'delegates',
            'value': ['vote_on_motion', True]
        })


send_batch_1()
# send_batch_2()
# send_batch_3()

# send_tx(jeffie, 'currency', 'transfer',
# 		{
# 			'amount': 100_010,
# 			'to': 'stu'
# 		})