from argparse import ArgumentParser
from checksumdir import dirhash
from contracting.client import ContractingClient
from contracting.db.driver import FSDriver, ContractDriver
from contracting.db.encoder import decode
from hashlib import sha3_256
from lamden.contracts import sync
from lamden.crypto.canonical import block_hash_from_block
from lamden.crypto.wallet import Wallet
from lamden.logger.base import get_logger
from lamden.storage import BlockStorage
from lamden.utils.legacy import BLOCK_HASH_KEY, BLOCK_NUM_HEIGHT
from os import listdir
from pymongo import MongoClient
import json
import pathlib
import sys

GENESIS_HLC = '0000-00-00T00:00:00.000000000Z_0'
GENESIS_NUMBER = 0
GENESIS_PREV = 64 * '0'

def confirm_and_flush_blocks(bs: BlockStorage) -> bool:
    if bs.total_blocks() > 0:
        i = ''
        while i != 'y' and i != 'n':
            i = input(f'Confirm deletion of block data located under {bs.root} (y/n)\n> ')
        if i == 'y':
            bs.flush()
        else:
            return False
    
    return True

def confirm_and_flush_state(state: FSDriver) -> bool:
    if len(listdir(state.root)) > 0:
        i = ''
        while i != 'y' and i != 'n':
            i = input(f'Confirm deletion of state data located under {state.root} (y/n)\n> ')
        if i == 'y':
            state.flush()
        else:
            return False

    return True

def setup_genesis_contracts(contracting_client: ContractingClient):
    contracting_client.set_submission_contract()

    constitution = None
    with open(pathlib.Path.home().joinpath('constitution.json')) as f:
        constitution = json.load(f)

    sync.setup_genesis_contracts(
        initial_masternodes=constitution['masternodes'],
        initial_delegates=constitution['delegates'],
        client=contracting_client
    )

if __name__ == '__main__':
    log = get_logger('GENESIS_BLOCK')
    parser = ArgumentParser()
    parser.add_argument('-k', '--key', type=str, required=True)
    parser.add_argument('--migrate', choices=['none', 'mongo', 'filesystem'], required=True)
    args = parser.parse_args()

    founders_wallet = Wallet(seed=bytes.fromhex(args.key))

    genesis_block = {
        'hash': block_hash_from_block(GENESIS_HLC, GENESIS_NUMBER, GENESIS_PREV),
        'number': GENESIS_NUMBER,
        'hlc_timestamp': GENESIS_HLC,
        'previous': GENESIS_PREV,
        'genesis': [],
        'origin': {
            'signature': '',
            'signer': ''
        },
        'state_hash': ''
    }

    
    bs = BlockStorage()
    state = FSDriver()
    contract_driver = ContractDriver(driver=state)
    contracting_client = ContractingClient(driver=contract_driver, submission_filename=sync.DEFAULT_SUBMISSION_PATH)

    if not confirm_and_flush_blocks(bs):
        log.info('Aborting')
        sys.exit(1)

    if args.migrate == 'filesystem':
        sync.flush_sys_contracts(client=contracting_client)
        log.info('Flushed genesis contracts')
    else:
        if not confirm_and_flush_state(state):
            log.info('Aborting')
            sys.exit(1)

    log.info('Setting up genesis contracts...')
    setup_genesis_contracts(contracting_client)

    log.info('Adding genesis contracts state changes to genesis block...')
    for key in state.keys():
        genesis_block['genesis'].append({
            'key': key,
            'value': state.get(key)
        })

    if args.migrate == 'mongo':
        mongo_skip_keys = state.keys() + [BLOCK_HASH_KEY, BLOCK_NUM_HEIGHT]
        client = MongoClient()
        log.info('Migrating state data from mongo and filling genesis block...')
        for record in client.lamden.state.find({'_id': {'$nin': mongo_skip_keys}}):
            try:
                state.set(record['_id'], decode(record['v']))
                genesis_block['genesis'].append({
                    'key': record['_id'],
                    'value': decode(record['v'])
                })
            except ValueError as err:
                log.error(f'Skipped key: "{record["_id"]}", due to error: {err}')

    log.info('Sorting state changes inside genesis block...')
    genesis_block['genesis'] = sorted(genesis_block['genesis'], key=lambda d: d['key'])

    log.info('Computing state storage hash...')
    genesis_block['state_hash'] = dirhash(state.root)

    log.info('Signing state changes...')
    h = sha3_256()
    h.update('{}'.format(genesis_block['genesis']).encode())
    genesis_block['origin']['signer'] = founders_wallet.verifying_key
    genesis_block['origin']['signature'] = founders_wallet.sign(h.hexdigest())

    log.info('Storing genesis block...')
    bs.store_genesis_block(genesis_block)

    # TODO: set latest block hash & height?
