from argparse import ArgumentParser
from contracting.client import ContractingClient
from contracting.db.driver import FSDriver, ContractDriver, CODE_KEY, COMPILED_KEY, OWNER_KEY, TIME_KEY, DEVELOPER_KEY
from contracting.db.encoder import encode, decode
from lamden.contracts import sync
from lamden.crypto.block_validator import GENESIS_BLOCK_NUMBER, GENESIS_HLC_TIMESTAMP, GENESIS_PREVIOUS_HASH
from lamden.crypto.canonical import block_hash_from_block, hash_genesis_block_state_changes
from lamden.crypto.wallet import Wallet
from lamden.logger.base import get_logger
from lamden.storage import LATEST_BLOCK_HASH_KEY, LATEST_BLOCK_HEIGHT_KEY, STORAGE_HOME
from lamden.utils.legacy import BLOCK_HASH_KEY, BLOCK_NUM_HEIGHT
from pymongo import MongoClient
import json
import pathlib
import shutil
import sys

GENESIS_CONTRACTS = ['currency', 'election_house', 'stamp_cost', 'rewards', 'upgrade', 'foundation', 'masternodes', 'delegates', 'elect_masternodes', 'elect_delegates']
GENESIS_CONTRACTS_KEYS = [contract + '.' + key for key in [CODE_KEY, COMPILED_KEY, OWNER_KEY, TIME_KEY, DEVELOPER_KEY] for contract in GENESIS_CONTRACTS]
GENESIS_BLOCK_PATH = pathlib.Path().home().joinpath('genesis_block.json')
GENESIS_STATE_PATH = STORAGE_HOME.joinpath('tmp_genesis_block_state')
LOG = get_logger('GENESIS_BLOCK')

def setup_genesis_contracts(contracting_client: ContractingClient):
    state_changes = {}

    contracting_client.set_submission_contract(filename=sync.DEFAULT_SUBMISSION_PATH, commit=False)
    state_changes.update(contracting_client.raw_driver.pending_writes)
    contracting_client.raw_driver.commit()
    contracting_client.submission_contract = contracting_client.get_contract('submission')

    constitution = None
    with open(pathlib.Path.home().joinpath('constitution.json')) as f:
        constitution = json.load(f)

    sync.setup_genesis_contracts(
        initial_masternodes=[vk for vk in constitution['masternodes'].keys()] + [vk for vk in constitution['delegates'].keys()],
        initial_delegates=[vk for vk in constitution['delegates'].keys()],
        client=contracting_client,
        commit=False
    )

    state_changes.update(contracting_client.raw_driver.pending_writes)
    contracting_client.raw_driver.commit()

    return {k: v for k, v in state_changes.items() if v is not None}

def build_block(
    founder_sk: str,
    migration_scheme: str,
    contracting_client: ContractingClient,
    db: str = '',
    collection: str = '',
    existing_state_driver: FSDriver = None
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

    LOG.info('Setting up genesis contracts...')
    state_changes = setup_genesis_contracts(contracting_client)
    for key, value in state_changes.items():
        genesis_block['genesis'].append({
            'key': key,
            'value': value
        })

    LOG.info('Setting latest block hash & height...')
    genesis_block['genesis'].append({'key': LATEST_BLOCK_HEIGHT_KEY, 'value': genesis_block['number']})
    genesis_block['genesis'].append({'key': LATEST_BLOCK_HASH_KEY, 'value': genesis_block['hash']})

    if migration_scheme == 'filesystem':
        LOG.info('Migrating state data from filesystem and filling genesis block...')
        for key in existing_state_driver.keys():
            if key not in GENESIS_CONTRACTS_KEYS:
                entry = next((item for item in genesis_block['genesis'] if item['key'] == key), None)
                if entry is not None:
                    entry['value'] = existing_state_driver.get(key)
                else:
                    genesis_block['genesis'].append({
                        'key': key,
                        'value': existing_state_driver.get(key)
                    })
    
    elif migration_scheme == 'mongo':
        mongo_skip_keys = GENESIS_CONTRACTS_KEYS + [BLOCK_HASH_KEY, BLOCK_NUM_HEIGHT]
        client = MongoClient()
        LOG.info('Migrating state data from mongo and filling genesis block...')
        for record in client[db][collection].find({'_id': {'$nin': mongo_skip_keys}}):
            entry = next((item for item in genesis_block['genesis'] if item['key'] == record['_id']), None)
            if entry is not None:
                entry['value'] = decode(record['v'])
            else:
                genesis_block['genesis'].append({
                    'key': record['_id'],
                    'value': decode(record['v'])
                })

    LOG.info('Sorting state changes inside genesis block...')
    genesis_block['genesis'] = sorted(genesis_block['genesis'], key=lambda d: d['key'])

    LOG.info('Signing state changes...')
    founders_wallet = Wallet(seed=bytes.fromhex(founder_sk))
    genesis_block['origin']['sender'] = founders_wallet.verifying_key
    genesis_block['origin']['signature'] = founders_wallet.sign(hash_genesis_block_state_changes(genesis_block['genesis']))

    return genesis_block

def main(
    founder_sk: str,
    migration_scheme: str,
    contracting_client: ContractingClient,
    db: str = '',
    collection: str = '',
    existing_state_driver: FSDriver = None
):
    if GENESIS_BLOCK_PATH.is_file():
        LOG.error(f'"{GENESIS_BLOCK_PATH}" already exist')
        sys.exit(1)

    genesis_block = build_block(founder_sk, migration_scheme, contracting_client, db, collection, existing_state_driver)

    LOG.info(f'Saving genesis block to "{GENESIS_BLOCK_PATH}"...')
    with open(GENESIS_BLOCK_PATH, 'w') as f:
        f.write(encode(genesis_block))

    shutil.rmtree(GENESIS_STATE_PATH)

if __name__ == '__main__':
    parser = ArgumentParser()
    parser.add_argument('-k', '--key', type=str, required=True)
    parser.add_argument('--migrate', default='none', choices=['mongo', 'filesystem'])
    parser.add_argument('--db', type=str)
    parser.add_argument('--collection', type=str)
    args = parser.parse_args()

    state = FSDriver(GENESIS_STATE_PATH)
    contract_driver = ContractDriver(driver=state)
    contracting_client = ContractingClient(driver=contract_driver, submission_filename=sync.DEFAULT_SUBMISSION_PATH)
    db = args.db if args.migrate == 'mongo' else ''
    collection = args.collection if args.migrate == 'mongo' else ''
    existing_state_driver = FSDriver() if args.migrate == 'filesystem' else None

    main(args.key, args.migrate, contracting_client, db=db, collection=collection, existing_state_driver=existing_state_driver)
