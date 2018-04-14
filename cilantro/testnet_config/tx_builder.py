import requests
from cilantro import Constants
from cilantro.messages import StandardTransaction, StandardTransactionBuilder, TransactionContainer, VoteTransaction, VoteTransactionBuilder, SwapTransaction, SwapTransactionBuilder
from cilantro.db.delegate.backend import *
from cilantro.utils import Encoder as E
from cilantro.logger import get_logger

MN_URL = 'http://127.0.0.1:8080'

STU = ('db929395f15937f023b4682995634b9dc19b1a2b32799f1f67d6f080b742cdb1',
 '324ee2e3544a8853a3c5a0ef0946b929aa488cbe7e7ee31a0fef9585ce398502')
DAVIS = ('21fee38471799f8c2989dd81c6d46f6c2e2db6caf63efa98a093fcba064a4b62',
 'a103715914a7aae8dd8fddba945ab63a169dfe6e37f79b4a58bcf85bfd681694')
DENTON = ('9decc7f7f0b5a4fc87ab5ce700e2d6c5d51b7565923d50ea13cbf78031bb3acf',
 '20da05fdba92449732b3871cc542a058075446fedb41430ee882e99f9091cc4d')
KNOWN_ADRS = (STU, DAVIS, DENTON)

def send_tx(sender, receiver, amount):
    if sender not in KNOWN_ADRS:
        raise ValueError("Unknown address {} not in preloaded wallets".format(sender))
    if type(receiver) is tuple:
        receiver = receiver[1]

    tx = StandardTransactionBuilder.create_tx(sender[0], sender[1], receiver, amount)
    # r = requests.post(MN_URL, data=Envelope.create(tx).serialize())
    r = requests.post(MN_URL, data=TransactionContainer.create(tx).serialize())
    print("Request status code: {}".format(r.status_code))



def seed_wallets(amount=10000):
    for i in range(len(Constants.Testnet.Delegates)):
        backend = LevelDBBackend(path=PATH + '_' + str(i))
        for wallet in KNOWN_ADRS:
            stored_amount = E.encode(amount * pow(10, Constants.Protocol.DecimalPrecision))
            backend.set(BALANCES, wallet[1].encode(), stored_amount)
            log = get_logger('WALLET SEEDER')
            log.info(backend.get(BALANCES, wallet[1].encode()))


def send_vote():
    tx = VoteTransactionBuilder.random_tx()
    r = requests.post(MN_URL, data=TransactionContainer.create(tx).serialize())

# def send_swap():
#     tx = SwapTransactionBuilder.random_tx()
#     r = requests.post(MN_URL, data=Envelope.create(tx).serialize())