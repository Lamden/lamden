import requests
from cilantro import Constants
from cilantro.messages import StandardTransaction, StandardTransactionBuilder
from cilantro.db.delegate.backend import *
from cilantro.utils import Encoder as E
from cilantro.logger import get_logger

MN_URL = 'http://127.0.0.1:8080'

STU = ('c80a483cb0d141893f02a805ba6baa822651d18b1976e52b0e485d571e9b210e40062e4c5a0887ca907278cdcb16688ec446a37adea909e4ccae63acb3b12083',
 '40062e4c5a0887ca907278cdcb16688ec446a37adea909e4ccae63acb3b12083')
DAVIS = ('3808074e565b7b1f80cb13c4e887b9812885f63a36fed2e18c3e132f576b357a10d86d0e14dbf77449c4d287312588fd61f5a4f10533bc4ae4df49c7e35ad5bc',
 '10d86d0e14dbf77449c4d287312588fd61f5a4f10533bc4ae4df49c7e35ad5bc')

KNOWN_ADRS = (STU, DAVIS)


def send_tx(sender, receiver, amount):
    if sender not in KNOWN_ADRS:
        raise ValueError("Unknown address {} not in preloaded wallets".format(sender))

    tx = StandardTransactionBuilder.create_tx(sender[0], sender[1], receiver, amount)
    r = requests.post(MN_URL, data=tx.serialize())


def seed_wallets(amount=10000):
    for i in range(len(Constants.Testnet.Delegates)):
        backend = LevelDBBackend(path=PATH + '_' + str(i))
        for wallet in KNOWN_ADRS:
            stored_amount = E.encode(amount * pow(10, Constants.Protocol.DecimalPrecision))
            backend.set(BALANCES, wallet[1].encode(), stored_amount)
            log = get_logger('WALLET SEEDER')
            log.info(backend.get(BALANCES, wallet[1].encode()))
