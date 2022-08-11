from argparse import ArgumentParser
from contracting.client import ContractingClient
from contracting.db.driver import FSDriver, ContractDriver, CODE_KEY, COMPILED_KEY, OWNER_KEY, TIME_KEY, DEVELOPER_KEY, FSDRIVER_HOME
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
from pathlib import Path
import shutil
import sys

GENESIS_CONTRACTS = ['currency', 'election_house', 'stamp_cost', 'rewards', 'upgrade', 'foundation', 'masternodes', 'delegates', 'elect_masternodes', 'elect_delegates']
GENESIS_CONTRACTS_KEYS = [contract + '.' + key for key in [CODE_KEY, COMPILED_KEY, OWNER_KEY, TIME_KEY, DEVELOPER_KEY] for contract in GENESIS_CONTRACTS]
GENESIS_BLOCK_PATH = Path().home().joinpath('genesis_block.json')
GENESIS_STATE_PATH = Path('/tmp/tmp_state')
LOG = get_logger('GENESIS_BLOCK')

def build_genesis_contracts_changes():
    state_changes = {}
    contracting_client = ContractingClient(driver=ContractDriver(FSDriver(root=GENESIS_STATE_PATH)), submission_filename=sync.DEFAULT_SUBMISSION_PATH)

    contracting_client.set_submission_contract(filename=sync.DEFAULT_SUBMISSION_PATH, commit=False)
    state_changes.update(contracting_client.raw_driver.pending_writes)

    contracting_client.raw_driver.commit()
    contracting_client.submission_contract = contracting_client.get_contract('submission')

    constitution = None
    with open(Path.home().joinpath('constitution.json')) as f:
        constitution = json.load(f)

    sync.setup_genesis_contracts(
        initial_masternodes=[vk for vk in constitution['masternodes'].keys()] + [vk for vk in constitution['delegates'].keys()],
        initial_delegates=[vk for vk in constitution['delegates'].keys()],
        client=contracting_client,
        commit=False
    )

    state_changes.update(contracting_client.raw_driver.pending_writes)

    contracting_client.flush()

    return {k: v for k, v in state_changes.items() if v is not None}

def fetch_filebased_state(filebased_state_path: Path, ignore_keys: list = []):
    state = []
    driver = FSDriver(root=filebased_state_path)
    for key in driver.keys():
        if key not in ignore_keys:
            state.append({
                'key': key,
                'value': driver.get(key)
            })

    return state

def fetch_mongo_state(db: str, collection: str, ignore_keys: list = []):
    state = []
    client = MongoClient()
    for record in client[db][collection].find({'_id': {'$nin': ignore_keys}}):
        state.append({
            'key': record['_id'],
            'value': decode(record['v'])
        })

    return state

def build_block(founder_sk: str, additional_state: list):
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

    LOG.info('Building genesis contracts state...')
    state_changes = build_genesis_contracts_changes()
    for key, value in state_changes.items():
        genesis_block['genesis'].append({
            'key': key,
            'value': value
        })

    LOG.info('Setting latest block hash & height...')
    genesis_block['genesis'].append({'key': LATEST_BLOCK_HEIGHT_KEY, 'value': genesis_block['number']})
    genesis_block['genesis'].append({'key': LATEST_BLOCK_HASH_KEY, 'value': genesis_block['hash']})

    LOG.info('Adding additional state...')
    for delta in additional_state:
        entry = next((item for item in genesis_block['genesis'] if item['key'] == delta['key']), None)
        if entry is not None:
            entry['value'] = delta['value']
        else:
            genesis_block['genesis'].append(delta)

    LOG.info('Sorting state changes inside genesis block...')
    genesis_block['genesis'] = sorted(genesis_block['genesis'], key=lambda d: d['key'])

    LOG.info('Signing state changes...')
    founders_wallet = Wallet(seed=bytes.fromhex(founder_sk))
    genesis_block['origin']['sender'] = founders_wallet.verifying_key
    genesis_block['origin']['signature'] = founders_wallet.sign(hash_genesis_block_state_changes(genesis_block['genesis']))

    return genesis_block

def main(
    founder_sk: str,
    migration_scheme: str = None,
    db: str = '',
    collection: str = '',
    filebased_state_path: Path = None
):
    if GENESIS_BLOCK_PATH.is_file():
        LOG.error(f'"{GENESIS_BLOCK_PATH}" already exist')
        sys.exit(1)

    additional_state = []
    if migration_scheme == 'filesystem':
        additional_state = fetch_filebased_state(filebased_state_path, ignore_keys=GENESIS_CONTRACTS_KEYS)
    elif migration_scheme == 'mongo':
        additional_state = fetch_mongo_state(db, collection, ignore_keys=GENESIS_CONTRACTS_KEYS + [BLOCK_HASH_KEY, BLOCK_NUM_HEIGHT])

    genesis_block = build_block(founder_sk, additional_state)

    LOG.info(f'Saving genesis block to "{GENESIS_BLOCK_PATH}"...')
    with open(GENESIS_BLOCK_PATH, 'w') as f:
        f.write(encode(genesis_block))

if __name__ == '__main__':
    parser = ArgumentParser()
    parser.add_argument('-k', '--key', type=str, required=True)
    parser.add_argument('--migrate', default='none', choices=['mongo', 'filesystem'])
    parser.add_argument('--db', type=str)
    parser.add_argument('--collection', type=str)
    args = parser.parse_args()

    db = args.db if args.migrate == 'mongo' else ''
    collection = args.collection if args.migrate == 'mongo' else ''
    filebased_state_path = FSDRIVER_HOME if args.migrate == 'filesystem' else None

    main(args.key, args.migrate, db=db, collection=collection, filebased_state_path=filebased_state_path)
