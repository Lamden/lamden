from argparse import ArgumentParser
from checksumdir import dirhash
from contracting.client import ContractingClient
from contracting.db.driver import FSDriver, ContractDriver, CODE_KEY
from contracting.db.encoder import decode
from lamden.contracts import sync
from lamden.crypto.block_validator import GENESIS_BLOCK_NUMBER, GENESIS_HLC_TIMESTAMP, GENESIS_PREVIOUS_HASH
from lamden.crypto.canonical import block_hash_from_block, hash_genesis_block_state_changes
from lamden.crypto.wallet import Wallet
from lamden.logger.base import get_logger
from lamden.storage import BlockStorage
from lamden.utils.legacy import BLOCK_HASH_KEY, BLOCK_NUM_HEIGHT
from os import listdir
from pymongo import MongoClient
import json
import pathlib
import sys

GENESIS_CONTRACTS = ['currency', 'election_house', 'stamp_cost', 'rewards', 'upgrade', 'foundation']
LOG = get_logger('GENESIS_BLOCK')

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

def main(
    founder_sk: str,
    migration_scheme: str,
    bs: BlockStorage,
    state: FSDriver,
    contract_driver: ContractDriver,
    contracting_client: ContractingClient
):
    genesis_block = {
        'hash': block_hash_from_block(GENESIS_HLC_TIMESTAMP, GENESIS_BLOCK_NUMBER, GENESIS_PREVIOUS_HASH),
        'number': GENESIS_BLOCK_NUMBER,
        'hlc_timestamp': GENESIS_HLC_TIMESTAMP,
        'previous': GENESIS_PREVIOUS_HASH,
        'genesis': [],
        'origin': {
            'signature': '',
            'sender': ''
        }
    }

    if not confirm_and_flush_blocks(bs):
        LOG.info('Aborting')
        sys.exit(1)

    if migration_scheme == 'filesystem':
        for con in GENESIS_CONTRACTS:
            state.delete(con + '.' + CODE_KEY)
        LOG.info('Flushed genesis contracts')
    else:
        if not confirm_and_flush_state(state):
            LOG.info('Aborting')
            sys.exit(1)

    LOG.info('Setting up genesis contracts...')
    setup_genesis_contracts(contracting_client)

    LOG.info('Filling genesis block...')
    for key in state.keys():
        genesis_block['genesis'].append({
            'key': key,
            'value': state.get(key)
        })

    if migration_scheme == 'mongo':
        mongo_skip_keys = state.keys() + [BLOCK_HASH_KEY, BLOCK_NUM_HEIGHT]
        client = MongoClient()
        LOG.info('Migrating state data from mongo and filling genesis block...')
        for record in client.lamden.state.find({'_id': {'$nin': mongo_skip_keys}}):
            try:
                state.set(record['_id'], decode(record['v']))
                genesis_block['genesis'].append({
                    'key': record['_id'],
                    'value': decode(record['v'])
                })
            except ValueError as err:
                LOG.error(f'Skipped key: "{record["_id"]}", due to error: {err}')

    LOG.info('Sorting state changes inside genesis block...')
    genesis_block['genesis'] = sorted(genesis_block['genesis'], key=lambda d: d['key'])

    # TODO: do we want to have this?
    # LOG.info('Computing state storage hash...')
    # genesis_block['state_hash'] = dirhash(state.root, hashfunc='sha256')

    LOG.info('Signing state changes...')
    founders_wallet = Wallet(seed=bytes.fromhex(founder_sk))
    genesis_block['origin']['sender'] = founders_wallet.verifying_key
    genesis_block['origin']['signature'] = founders_wallet.sign(hash_genesis_block_state_changes(genesis_block['genesis']))

    LOG.info('Storing genesis block...')
    bs.store_block(genesis_block)

    # TODO: set latest block hash & height?

if __name__ == '__main__':
    parser = ArgumentParser()
    parser.add_argument('-k', '--key', type=str, required=True)
    parser.add_argument('--migrate', choices=['none', 'mongo', 'filesystem'], required=True)
    args = parser.parse_args()

    bs = BlockStorage()
    state = FSDriver()
    contract_driver = ContractDriver(driver=state)
    contracting_client = ContractingClient(driver=contract_driver, submission_filename=sync.DEFAULT_SUBMISSION_PATH)

    main(args.key, args.migrate, bs, state, contract_driver, contracting_client)
