from cilantro.nodes import Delegate
from cilantro.protocol.wallets import ED25519Wallet
from multiprocessing import Process
from cilantro.logger import get_logger

delegates = []

PORT_START = 5000
NUM_DELEGATES = 4

MULTI_PROC = True

# Delegates and wallets
for n in range(NUM_DELEGATES):
    sk, vk = ED25519Wallet.new()
    port = PORT_START + n
    delegates.append({'url': 'tcp://127.0.0.1', 'verifying_key': vk, 'signing_key': sk, 'port': port})

public_delegate_list = [{'url': d['url'], 'verifying_key': d['verifying_key'], 'port': d['port']} for d in delegates]

import signal
import sys

def signal_handler(signal, frame):
        print('You pressed Ctrl+C!')
        [d.subscriber_process.terminate() for d in delegate_objects]
        sys.exit(0)

def start_delelegate(url, port, delegates, sk):
    log = get_logger("DelegateFactory")
    log.debug("Instantiating a new delegate")
    d = Delegate(url=url, port=port, delegates=public_delegate_list, signing_key=sk)

if MULTI_PROC:
    print("Starting delegates on separate proccesses")
    for i in range(len(delegates)):
        d = delegates[i]
        p = Process(target=start_delelegate, args=(d['url'], d['port'], public_delegate_list, d['signing_key'],))
        p.start()
else:
    print("Starting delegate on same process")
    delegate_objects = []
    for delegate in delegates:
        d = Delegate(url=delegate['url'], port=delegate['port'], delegates=public_delegate_list, signing_key=delegate['signing_key'])
        delegate_objects.append(d)


signal.signal(signal.SIGINT, signal_handler)
print('Press Ctrl+C')
signal.pause()