from argparse import ArgumentParser
from contracting.client import ContractingClient
from contracting.db.driver import FSDriver, ContractDriver, CODE_KEY, COMPILED_KEY, OWNER_KEY, TIME_KEY, DEVELOPER_KEY
from contracting.db.encoder import encode, decode
from lamden.contracts import sync
from lamden.crypto.block_validator import GENESIS_BLOCK_NUMBER, GENESIS_HLC_TIMESTAMP, GENESIS_PREVIOUS_HASH
from lamden.crypto.canonical import block_hash_from_block, hash_genesis_block_state_changes
from lamden.crypto.wallet import Wallet
from lamden.logger.base import get_logger
from lamden.storage import LATEST_BLOCK_HASH_KEY, LATEST_BLOCK_HEIGHT_KEY
from lamden.utils.legacy import BLOCK_HASH_KEY, BLOCK_NUM_HEIGHT
from pathlib import Path
from pymongo import MongoClient
import json
import os
import re

GENESIS_CONTRACTS = ['submission', 'currency', 'election_house', 'stamp_cost', 'rewards', 'upgrade', 'foundation', 'masternodes', 'elect_masternodes']
GENESIS_CONTRACTS_KEYS = [contract + '.' + key for key in [CODE_KEY, COMPILED_KEY, OWNER_KEY, TIME_KEY, DEVELOPER_KEY] for contract in GENESIS_CONTRACTS]
MEMBERS_KEY = 'masternodes.S:members'
REWARDS_VALUE_KEY = 'rewards.S:value'
GENESIS_BLOCK_PATH = Path().home().joinpath('genesis_block.json')
TMP_STATE_PATH = Path('/tmp/tmp_state')
LOG = get_logger('GENESIS_BLOCK')

def build_genesis_contracts_changes(constitution_file_path: str = None, genesis_file_path: str = None, initial_members: list = None):
    state_changes = {}
    contracting_client = ContractingClient(driver=ContractDriver(FSDriver(root=TMP_STATE_PATH)), submission_filename=sync.DEFAULT_SUBMISSION_PATH)

    contracting_client.set_submission_contract(filename=sync.DEFAULT_SUBMISSION_PATH, commit=False)
    state_changes.update(contracting_client.raw_driver.pending_writes)

    contracting_client.raw_driver.commit()

    if initial_members is None:
        if constitution_file_path is not None:
            constitution_file_path = os.path.join(constitution_file_path, 'constitution.json')
            assert os.path.isfile(constitution_file_path), f'No constitution.json file found at: {constitution_file_path}'
        else:
            constitution_file_path = Path.home().joinpath('constitution.json')

        constitution = None
        with open(constitution_file_path) as f:
            constitution = json.load(f)

        if genesis_file_path is not None:
            genesis_file_path = os.path.join(genesis_file_path, 'genesis.json')
            assert os.path.isfile(genesis_file_path), f'No genesis.json file found at: {genesis_file_path}'

        initial_members = list(constitution['masternodes'].keys())

    sync.setup_genesis_contracts(
        initial_masternodes=initial_members,
        client=contracting_client,
        commit=False,
        filename=genesis_file_path
    )

    state_changes.update(contracting_client.raw_driver.pending_writes)

    contracting_client.raw_driver.flush()

    return {k: v for k, v in state_changes.items() if v is not None}

def should_ignore(key, ignore_keys):
    for ik in ignore_keys:
        if key.startswith(ik):
            return True

    return False

def fetch_filebased_state(filebased_state_path: Path, ignore_keys: list = []):
    LOG.info('Migrating existing file-based state...')
    state = {}
    driver = FSDriver(root=filebased_state_path)
    for key in driver.keys():
        if not should_ignore(key, ignore_keys):
            state[key] = driver.get(key)

    return state

def fetch_mongo_state(db: str, collection: str, ignore_keys: list = []):
    LOG.info('Migrating existing mongo state...')
    state = {}
    client = MongoClient()
    filter = {} if len(ignore_keys) == 0 else {'$and': [{'_id': {'$not': re.compile(f'^{key}')}} for key in ignore_keys]}
    for record in client[db][collection].find(filter):
        state[record['_id']] = decode(record['v'])

    return state

def repair_rewards(rewards_initial_split: list):
    if len(rewards_initial_split) == 5:
        rewards_initial_split.pop(0)
        rewards_initial_split[0] *= 2

def build_block(founder_sk: str, additional_state: dict = {}, constitution_file_path: str = None, genesis_file_path: str = None, initial_members: list = None):
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
    state_changes = build_genesis_contracts_changes(
        constitution_file_path=constitution_file_path,
        genesis_file_path=genesis_file_path,
        initial_members=initial_members
    )

    LOG.info('Merging additional state...')
    state_changes.update(additional_state)

    LOG.info('Filling genesis block...')
    for key, value in state_changes.items():
        if key == REWARDS_VALUE_KEY:
            repair_rewards(value)
        if key.startswith('con_muhwah') or len(key.split('.')[0]) >= 255:
            continue
        genesis_block['genesis'].append({
            'key': key,
            'value': value
        })

    LOG.info('Sorting state changes...')
    genesis_block['genesis'] = sorted(genesis_block['genesis'], key=lambda d: d['key'])

    LOG.info('Signing state changes...')
    founders_wallet = Wallet(seed=bytes.fromhex(founder_sk))
    genesis_block['origin']['sender'] = founders_wallet.verifying_key
    genesis_block['origin']['signature'] = founders_wallet.sign(hash_genesis_block_state_changes(genesis_block['genesis']))

    return genesis_block

def main(
    founder_sk: str,
    output_path: Path = None,
    constitution_path: Path = None,
    genesis_path: Path = None,
    migration_scheme: str = None,
    db: str = '',
    collection: str = '',
    filebased_state_path: Path = None
):
    output_path = output_path.joinpath('genesis_block.json') if output_path is not None else GENESIS_BLOCK_PATH
    assert not output_path.is_file(), f'"{output_path}" already exist'

    additional_state = {}
    if migration_scheme == 'filesystem':
        assert filebased_state_path is not None, 'invalid file-based state path provided'
        additional_state = fetch_filebased_state(filebased_state_path, ignore_keys=GENESIS_CONTRACTS_KEYS + [LATEST_BLOCK_HEIGHT_KEY, LATEST_BLOCK_HASH_KEY, MEMBERS_KEY])
    elif migration_scheme == 'mongo':
        assert db is not None and db != '', 'invalid database name provided'
        assert collection is not None and collection != '', 'invalid collection name provided'
        additional_state = fetch_mongo_state(db, collection, ignore_keys=GENESIS_CONTRACTS_KEYS + [BLOCK_HASH_KEY, BLOCK_NUM_HEIGHT, MEMBERS_KEY])

    genesis_block = build_block(founder_sk, additional_state, constitution_file_path=constitution_path, genesis_file_path=genesis_path)

    LOG.info(f'Saving genesis block to "{output_path}"...')
    with open(output_path, 'w') as f:
        f.write(encode(genesis_block))

if __name__ == '__main__':
    parser = ArgumentParser()
    parser.add_argument('-k', '--key', type=str, required=True)
    parser.add_argument('--output-path', type=str, required=False)
    parser.add_argument('--constitution-path', type=str, required=False)
    parser.add_argument('--genesis-path', type=str, required=False)
    parser.add_argument('--migrate', default='none', choices=['mongo', 'filesystem'])
    parser.add_argument('--db', type=str)
    parser.add_argument('--collection', type=str)
    parser.add_argument('--sp', '--state-path', type=str)
    args = parser.parse_args()

    main(founder_sk=args.key,
         output_path=Path(args.output_path) if args.output_path is not None else None,
         constitution_path=Path(args.constitution_path) if args.constitution_path is not None else None,
         genesis_path=Path(args.genesis_path) if args.genesis_path is not None else None,
         migration_scheme=args.migrate,
         db=args.db, collection=args.collection,
         filebased_state_path=Path(args.sp) if args.sp is not None else None)
