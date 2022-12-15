from lamden.crypto.transaction import build_transaction
from lamden.crypto.wallet import Wallet
import json
import logging
import os
import re
import requests
import subprocess
import time
import websocket

log = logging.getLogger('UPGRADE')

def validate_ip_address(ip_str):
    pattern = r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$"
    match = re.search(pattern, ip_str)

    return True if match else False

def on_message(ws, message):
    log.info(f'received message: {message}')
    message = json.loads(message)
    if message.get('event') == 'upgrade':
        message = message.get('data')
        if not validate_ip_address(message.get('bootnode_ip')):
            raise AttributeError('Invalid ip')
        os.environ['LAMDEN_BOOTNODE'] = message.get('bootnode_ip')
        os.environ['LAMDEN_BRANCH'] = message.get('lamden_branch')
        os.environ['CONTRACTING_BRANCH'] = message.get('contracting_branch')

        subprocess.check_call(['make', 'upgrade'])
        time.sleep(30)

        url = f'http://{message.get("bootnode_ip")}:18080'
        w = Wallet(seed=bytes.fromhex(os.environ['LAMDEN_SK']))
        nonce = json.loads(requests.get(f'{url}/nonce/{w.verifying_key}').text)['nonce']
        tx = build_transaction(
            w,
            contract='upgrade', function='pass_the_baton',
            kwargs={},
            nonce=nonce,
            processor=message.get('bootnode_vk'),
            stamps=500
        )
        requests.post(url, data=tx).json()

def on_error(ws, error):
    log.info(f'Connection error! Error: {error}')

if __name__ == "__main__":
    ws = websocket.WebSocketApp("ws://localhost:18080/", on_message=on_message, on_error=on_error)
    ws.run_forever()
