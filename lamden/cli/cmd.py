from contracting.db.encoder import decode
from lamden.crypto.wallet import Wallet
from lamden.logger.base import get_logger
from lamden.nodes.base import Node
from lamden.storage import STORAGE_HOME

from lamden.utils.add_block_num_to_state import AddBlockNum
from lamden.utils.migrate_blocks_dir import MigrateFiles

import argparse
import asyncio
import json
import os
import pathlib
import requests
import signal

logger = get_logger('STARTUP')

logger.info('''
            ##
          ######
        ####  ####
      ####      ####
    ####          ####
  ####              ####
#### ~ L A M D E N ~ ####
  ####             ####
    ####          ####
      ####      ####
        ####  ####
          ######
            ##
''')

def is_valid_ip(s):
    components = s.split('.')
    if len(components) != 4:
        return False

    for component in components:
        if int(component) > 255:
            return False

    return True

def resolve_constitution(fp):
    path = pathlib.PosixPath(fp).expanduser()

    path.touch()

    f = open(str(path), 'r')
    j = json.load(f)
    f.close()

    formatted_bootnodes = {}
    for vk, ip in j['masternodes'].items():
        assert is_valid_ip(ip), 'Invalid IP string provided to boot node argument.'
        formatted_bootnodes[vk] = f'tcp://{ip}'

    return formatted_bootnodes

def resolve_genesis_block(fp):
    path = pathlib.PosixPath(fp).expanduser()

    path.touch()

    f = open(str(path), 'r')
    genesis_block = decode(f.read())
    f.close()

    return genesis_block

def setup_node_signal_handler(node, loop):
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, lambda: asyncio.ensure_future(node.stop()))

def start_node(args):
    sk = bytes.fromhex(os.environ['LAMDEN_SK'])
    wallet = Wallet(seed=sk)

    logger.info(f'Node vk: {wallet.verifying_key}, ip: {requests.get("http://api.ipify.org").text}')

    constitution = resolve_constitution(args.constitution)
    constitution.pop(wallet.verifying_key, None)
    if len(constitution) > 0:
        logger.info(f'Constitution: {constitution}')

    genesis_block = resolve_genesis_block(args.genesis_block)

    n = Node(
        debug=args.debug,
        wallet=wallet,
        bootnodes=constitution,
        genesis_block=genesis_block,
        metering=True
    )

    loop = asyncio.get_event_loop()
    setup_node_signal_handler(n, loop)
    asyncio.ensure_future(n.start())
    loop.run_forever()


def join_network(args):
    sk = bytes.fromhex(os.environ['LAMDEN_SK'])
    wallet = Wallet(seed=sk)

    logger.info(f'Node vk: {wallet.verifying_key}, ip: {requests.get("http://api.ipify.org").text}')

    bootnode_ips = os.environ['LAMDEN_BOOTNODES'].split(':')
    bootnodes = {}
    for ip in bootnode_ips:
        resp = requests.get(f'http://{ip}:18080/id').json()
        vk = resp.get('verifying_key')
        if vk is not None:
            bootnodes[vk] = f'tcp://{ip}:19000'
    assert len(bootnodes) > 0, 'Must provide at least one bootnode.'
    logger.info(f'Bootnodes: {bootnodes}')

    n = Node(
        debug=args.debug,
        wallet=wallet,
        bootnodes=bootnodes,
        join=True,
        metering=True
    )

    loop = asyncio.get_event_loop()
    setup_node_signal_handler(n, loop)
    asyncio.ensure_future(n.start())
    loop.run_forever()

def setup_lamden_parser(parser):
    subparser = parser.add_subparsers(title='subcommands', description='Lamden commands',
                                      help='Shows set of commands', dest='command')

    start_parser = subparser.add_parser('start')
    start_parser.add_argument('-c', '--constitution', type=str, default='~/constitution.json')
    start_parser.add_argument('-gb', '--genesis_block', type=str, default='~/genesis_block.json')
    start_parser.add_argument('-d', '--debug', type=bool, default=False)

    join_parser = subparser.add_parser('join')
    join_parser.add_argument('-d', '--debug', type=bool, default=False)

def migrate_storage():
    blocks_alias_dir_new = os.path.join(STORAGE_HOME, 'blocks_alias')
    txs_dir_new = os.path.join(STORAGE_HOME, 'txs')

    blocks_dir = os.path.join(STORAGE_HOME, 'blocks')
    blocks_alias_dir_old = os.path.join(blocks_dir, 'alias')
    txs_dir_old = os.path.join(blocks_dir, 'txs')

    if (
            not os.path.exists(blocks_alias_dir_new)
            and not os.path.exists(txs_dir_new)
            and os.path.exists(blocks_alias_dir_old)
            and os.path.exists(txs_dir_old)
    ):
        logger.warning("Migrating Old Storage to New Storage...")

        migrate_from = os.path.join(STORAGE_HOME, 'blocks')
        migrate_temp = os.path.join(STORAGE_HOME, 'migrating')

        storage_migration = MigrateFiles(src_path=migrate_from, dest_path=migrate_temp)
        storage_migration.start()

        logger.info("Completed Block Migration! \n")

        logger.warning("Adding Block Numbers to state....")

        block_num_adder = AddBlockNum(lamden_root=STORAGE_HOME)
        block_num_adder.start()

        logger.info("Completed Adding Block Numbers to State! \n")




# do nothing if the directory doesn't exist

def main():
    parser = argparse.ArgumentParser(description="Lamden Commands", prog='lamden')
    setup_lamden_parser(parser)
    args = parser.parse_args()

    print(args)

    if vars(args).get('command') is None:
        return

    migrate_storage()

    if args.command == 'start':
        start_node(args)
    elif args.command == 'join':
        join_network(args)

if __name__ == '__main__':
    main()