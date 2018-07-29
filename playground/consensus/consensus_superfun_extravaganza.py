from cilantro.nodes import Delegate
from cilantro.protocol.wallet import Wallet
from multiprocessing import Process
from cilantro.logger import get_logger
import signal
import sys
import time


PORT_START = 4650
NUM_DELEGATES = 4
MULTI_PROC = True  # NOTE: True is not working atm (reactor wont get notify_ready() for some reason)

URL_BASE = 'ipc://127.0.0.1'

delegates = []
log = get_logger("DelegateFactory")
log.info("MAIN THREAD")

# Delegates and wallets
for n in range(NUM_DELEGATES):
    sk, vk = Wallet.new()
    port = PORT_START + n
    url = "{}:{}".format(URL_BASE, port)
    # delegates.append({'url': 'ipc://127.0.0.1', 'verifying_key': vk, 'signing_key': sk, 'port': port})
    delegates.append({'url': url, 'verifying_key': vk, 'signing_key': sk})

# public_delegate_list = [{'url': d['url'], 'verifying_key': d['verifying_key']} for d in delegates]
public_delegates = {d['url']: d['verifying_key'] for d in delegates}


def signal_handler(signal, frame):
        log.debug('You pressed Ctrl+C!')
        [d.subscriber_process.terminate() for d in delegate_objects]
        sys.exit(0)

def start_delelegate(url, delegates, sk):
    log.debug("Instantiating a new delegate")
    d = Delegate(url=url, delegates=public_delegates, signing_key=sk)
    signal.pause()


if __name__ == "__main__":
    log.info("MAIN THREAD")

    if MULTI_PROC:
        log.debug("Starting delegates on separate proccesses")
        for i in range(len(delegates)):
            d = delegates[i]
            p = Process(target=start_delelegate, args=(d['url'], public_delegates, d['signing_key']))
            p.start()
        signal.pause()
    else:
        log.debug("Starting delegate on same process")
        delegate_objects = []
        for delegate in delegates:
            d = Delegate(url=delegate['url'], delegates=public_delegates, signing_key=delegate['signing_key'])
            delegate_objects.append(d)

    signal.signal(signal.SIGINT, signal_handler)
    signal.pause()