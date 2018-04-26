from cilantro import Constants
from cilantro.nodes import Delegate, Masternode, Witness
from cilantro.testnet_config.tx_builder import *
from cilantro.db.delegate import DB, DB_NAME
from multiprocessing import Process
from cilantro.logger import get_logger
import signal
import sys
import time

"""
If running this on PyCharm, be sure enable to console output to see glorious colors. 
Go to the run dropdown in top right, 'Edit Configurations', and then check 'Emulate Terminal output in Console'

One can edit the number of Delegates/Witnesses in config.json (although multiple witnesses currently not supported)

To send TX through the network, open up a python terminal and run 
-- from cilantro.testnet_config.tx_builder import *
Then, before sending tx through the system, you must run
-- seed_wallets()
Then you can send standard transactions using
-- send_tx(DENTON, DAVIS, 420.42)  # works with DENTON, STU, and DAVIS  
"""

MULTI_PROC = True

START_MASTERNODE = True
START_WITNESS = True
START_DELEGATES = True


log = get_logger("TestnetBootstrap")


def signal_handler(signal, frame):
        log.debug('You pressed Ctrl+C!')
        sys.exit(0)


def start_delelegate(i):
    def seed_wallets(amount=10000):
        log.critical("Seeding wallets with amount {}".format(amount))
        with DB('{}_{}'.format(DB_NAME, i)) as db:
            log.critical("GOT DB WITH NAME: {}".format(db.db_name))
            for wallet in KNOWN_ADRS:
                q = insert(db.tables.balances).values(wallet=wallet[1].encode(), amount=amount)
                db.execute(q)

    log = get_logger("DelegateFactory")
    db_name = DB_NAME + '_' + str(i)
    log.critical("\n***Instantiating a new delegate on slot {} with db name: {}\n".format(i, db_name))

    log.critical("Seeding wallets...")
    DB.set_context(db_name)
    seed_wallets()

    d = Delegate(slot=i)
    signal.pause()


def start_mn():
    log = get_logger("MasternodeFactor")
    log.critical("\n***Starting Masternode\n")
    mn = Masternode()
    signal.pause()


def start_witness(i):
    log = get_logger("MasternodeFactor")
    log.critical("Starting witness on slot {}".format(i))
    witness = Witness(slot=i)
    signal.pause()


if __name__ == "__main__":
    mn, witness, delegates = None, None, []

    if START_MASTERNODE:
        log.info("Starting Masternode")
        p = Process(target=start_mn)
        p.start()

    if START_WITNESS:
        log.info("Starting {} witnesses".format(len(Constants.Testnet.Witnesses)))
        for i in range(len(Constants.Testnet.Witnesses)):
            p = Process(target=start_witness, args=(i,))
            p.start()

    if START_DELEGATES:
        if MULTI_PROC:
            log.debug("Starting delegates on separate proccesses")
            for i in range(len(Constants.Testnet.Delegates)):
                p = Process(target=start_delelegate, args=(i,))
                p.start()
            signal.pause()
        else:
            log.debug("Starting delegate on same process")
            for i in range(len(Constants.Testnet.Delegates)):
                d = Delegate(slot=i)
            signal.pause()

    signal.signal(signal.SIGINT, signal_handler)
    signal.pause()

