from cilantro import Constants
from cilantro.nodes import Delegate, Masternode, Witness
from cilantro.protocol.wallets import ED25519Wallet
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
    log.info("Instantiating a new delegate")
    d = Delegate(slot=i)
    signal.pause()

def start_mn():
    log.info("Starting Masternode")
    mn = Masternode()
    signal.pause()

if __name__ == "__main__":
    mn, witness, delegates = None, None, []

    if START_MASTERNODE:
        log.info("Starting Masternode")
        p = Process(target=start_mn)
        p.start()
    if START_WITNESS:
        log.info("Starting witness")
        witness = Witness()

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

