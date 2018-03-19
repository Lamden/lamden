from cilantro import Constants
from cilantro.nodes import Delegate
from cilantro.protocol.wallets import ED25519Wallet
from multiprocessing import Process
from cilantro.logger import get_logger
import signal
import sys
import time




MULTI_PROC = True  # NOTE: True is not working atm (reactor wont get notify_ready() for some reason)


log = get_logger("DelegateFactory")
log.info("MAIN THREAD")

def signal_handler(signal, frame):
        log.debug('You pressed Ctrl+C!')
        sys.exit(0)

def start_delelegate(i):
    log.debug("Instantiating a new delegate")
    d = Delegate(slot=i)
    signal.pause()


if __name__ == "__main__":
    log.info("MAIN THREAD")

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

