import requests
from cilantro import Constants
from cilantro.messages import StandardTransaction, StandardTransactionBuilder, Envelope, VoteTransaction, VoteTransactionBuilder, SwapTransaction, SwapTransactionBuilder
from cilantro.utils import Encoder as E
from cilantro.logger import get_logger
from cilantro.db.delegate import *

from cilantro.protocol.interpreters.queries import *


import os



MN_URL = "http://{}:8080".format(os.getenv('MASTERNODE', '127.0.0.1'))

STU = ('db929395f15937f023b4682995634b9dc19b1a2b32799f1f67d6f080b742cdb1',
 '324ee2e3544a8853a3c5a0ef0946b929aa488cbe7e7ee31a0fef9585ce398502')
DAVIS = ('21fee38471799f8c2989dd81c6d46f6c2e2db6caf63efa98a093fcba064a4b62',
 'a103715914a7aae8dd8fddba945ab63a169dfe6e37f79b4a58bcf85bfd681694')
DENTON = ('9decc7f7f0b5a4fc87ab5ce700e2d6c5d51b7565923d50ea13cbf78031bb3acf',
 '20da05fdba92449732b3871cc542a058075446fedb41430ee882e99f9091cc4d')
KNOWN_ADRS = (STU, DAVIS, DENTON)


def seed_wallets(amount=10000, i=0):
    log = get_logger("WalletSeeder")
    log.critical("Seeding wallets with amount {}".format(amount))
    with DB('{}_{}'.format(DB_NAME, i)) as db:
        log.critical("GOT DB WITH NAME: {}".format(db.db_name))
        for wallet in KNOWN_ADRS:
            q = insert(db.tables.balances).values(wallet=wallet[1].encode(), amount=amount)
            db.execute(q)

def send_tx(sender, receiver, amount):
    if sender not in KNOWN_ADRS:
        raise ValueError("Unknown address {} not in preloaded wallets".format(sender))
    if type(receiver) is tuple:
        receiver = receiver[1]

    tx = StandardTransactionBuilder.create_tx(sender[0], sender[1], receiver, amount)
    r = requests.post(MN_URL, data=Envelope.create(tx).serialize())


def send_vote():
    tx = VoteTransactionBuilder.random_tx()
    r = requests.post(MN_URL, data=Envelope.create(tx).serialize())

# def send_swap():
#     tx = SwapTransactionBuilder.random_tx()
#     r = requests.post(MN_URL, data=Envelope.create(tx).serialize())