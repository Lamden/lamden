from cilantro.nodes import Delegate
from cilantro.protocol.wallets import ED25519Wallet

delegates = []

PORT_START = 5000
NUM_DELEGATES = 4

# Delegates and wallets
for n in range(NUM_DELEGATES):
    sk, vk = ED25519Wallet.new()
    port = PORT_START + n
    delegates.append({'url': 'tcp://127.0.0.1', 'verifying_key': vk, 'signing_key': sk, 'port': port})

public_delegate_list = [{'url': d['url'], 'verifying_key': d['verifying_key'], 'port': d['port']} for d in delegates]

delegate_objects = []
for delegate in delegates:
    d = Delegate(url=delegate['url'], port=delegate['port'], delegates=public_delegate_list, signing_key=delegate['signing_key'])
    delegate_objects.append(d)

import signal
import sys

def signal_handler(signal, frame):
        print('You pressed Ctrl+C!')
        [d.subscriber_process.terminate() for d in delegate_objects]
        sys.exit(0)


signal.signal(signal.SIGINT, signal_handler)
print('Press Ctrl+C')
signal.pause()