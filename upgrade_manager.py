from contracting.db.driver import FSDriver
from lamden.crypto.transaction import build_transaction
from lamden.crypto.wallet import Wallet
import json
import os
import pathlib
import requests
import subprocess
import time

w = Wallet(seed=bytes.fromhex(os.environ['LAMDEN_SK']))
d = FSDriver()

while True:
    if d.get('upgrade.upgrade_state:consensus'):
        print('Detected consensus...')
        node_list = d.get('masternodes.S:members')
        node_idx = d.get('upgrade.upgrade_state:node_index')
        if node_list[node_idx] == w.verifying_key:
            bootnode = node_list[(node_idx + 1) % len(node_list)]
            with open(pathlib.Path.home().joinpath('constitution.json')) as f:
                c = json.load(f)
                os.environ['LAMDEN_BOOTNODE'] = c['masternodes'][bootnode]
            os.environ['LAMDEN_BRANCH'] = d.get('upgrade.upgrade_state:lamden_branch_name')
            os.environ['CONTRACTING_BRANCH'] = d.get('upgrade.upgrade_state:contracting_branch_name')
            print('Done preparing the upgrade...')
            print(f'LAMDEN_BOOTNODE: {os.environ["LAMDEN_BOOTNODE"]}')
            print(f'LAMDEN_BRANCH: {os.environ["LAMDEN_BRANCH"]}')
            print(f'CONTRACTING_BRANCH: {os.environ["CONTRACTING_BRANCH"]}')

            subprocess.check_call(['make', 'upgrade'])
            time.sleep(30)
            print('Done upgrading, passing the baton...')
            url = f'http://{os.environ["LAMDEN_BOOTNODE"]}:18080'
            nonce = json.loads(requests.get(f'{url}/nonce/{w.verifying_key}').text)['nonce']
            tx = build_transaction(
                w,
                contract='upgrade', function='pass_the_baton',
                kwargs={},
                nonce=nonce,
                processor=bootnode,
                stamps=500
            )
            print(requests.post(url, data=tx).json())
        else:
            print('Not my turn yet...')
            time.sleep(30)
    else:
        print('No consensus...')
        time.sleep(30)
