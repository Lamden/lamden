import requests
import pathlib
import json
import os
import asyncio
import subprocess
from subprocess import call

from lamden.crypto.wallet import Wallet
from lamden.nodes.masternode.masternode import Masternode
from lamden.nodes.delegate.delegate import Delegate
from lamden.logger.base import get_logger

import time


def cfg_and_start_rsync_daemon():
    os.system('cp rsyncd.conf /etc/ && rsync --daemon > /dev/null 2>&1')

def print_ascii_art():
    print('''
                ##
              ######
            ####  ####
          ####      ####
        ####          ####
      ####              ####
        ####          ####
          ####      ####
            ####  ####
              ######
                ##

 ~ V I V A ~ L A ~ L A M D E N ! ~
''')


def clear():
    call('clear' if os.name == 'posix' else 'cls')


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

    assert 'masternodes' in j.keys(), 'No masternodes section.'
    assert 'delegates' in j.keys(), 'No delegates section.'

    const = {
        'masternodes': list(j['masternodes'].keys()),
        'delegates': list(j['delegates'].keys())
    }

    bootnodes = {**j['masternodes'], **j['delegates']}

    formatted_bootnodes = {}

    for vk, ip in bootnodes.items():
        assert is_valid_ip(ip), 'Invalid IP string provided to boot node argument.'
        formatted_bootnodes[vk] = f'tcp://{ip}'

    return const, formatted_bootnodes

def resolve_genesis_block(fp):
    path = pathlib.PosixPath(fp).expanduser()

    path.touch()

    f = open(str(path), 'r')
    genesis_block = json.load(f)
    f.close()

    return genesis_block


def resolve_raw_constitution(text):
    j = json.loads(text)

    assert 'masternodes' in j.keys(), 'No masternodes section.'
    assert 'masternode_min_quorum' in j.keys(), 'No masternode_min_quorum section.'
    assert 'delegates' in j.keys(), 'No delegates section.'
    assert 'delegate_min_quorum' in j.keys(), 'No delegate_min_quorum section.'

    return j


def start_node(args):
    logger = get_logger('STARTUP')
    logger.info({'node_type': args.node_type})

    assert args.node_type == 'masternode' or args.node_type == 'delegate', \
        'Provide node type as "masternode" or "delegate"'

    sk = bytes.fromhex(args.key)

    wallet = Wallet(seed=sk)

    logger.info({'node vk': wallet.verifying_key})

    const, bootnodes = resolve_constitution(args.constitution)
    genesis_block = resolve_genesis_block(args.genesis_block)

    logger.info({'constitution': const})
    logger.info({'bootnodes': bootnodes})

    assert len(bootnodes) > 0, 'Must provide at least one bootnode.'

    ip_str = requests.get('http://api.ipify.org').text
    socket_base = f'tcp://{ip_str}:19000'

    logger.info(f'socket_base: {socket_base}')

    # Setup Environment
    CURR_DIR = pathlib.Path(os.getcwd())
    os.environ['PKG_ROOT'] = str(CURR_DIR.parent)
    os.environ['CIL_PATH'] = os.environ.get('PKG_ROOT') + '/lamden'

    # Kill the
    if args.pid > -1:
        subprocess.check_call(['kill', '-15', str(args.pid)])

    if args.node_type == 'masternode':
        cfg_and_start_rsync_daemon()

        n = Masternode(
            debug=args.debug,
            wallet=wallet,
            socket_base=socket_base,
            bootnodes=bootnodes,
            constitution=const,
            webserver_port=args.webserver_port,
            bypass_catchup=args.bypass_catchup,
            node_type=args.node_type,
            genesis_block=genesis_block
        )
    elif args.node_type == 'delegate':
        n = Delegate(
            debug=args.debug,
            wallet=wallet,
            socket_base=socket_base,
            bootnodes=bootnodes,
            constitution=const,
            bypass_catchup=args.bypass_catchup,
            node_type=args.node_type,
            genesis_block=genesis_block
        )

    loop = asyncio.get_event_loop()
    asyncio.async(n.start())
    loop.run_forever()


def join_network(args):
    assert args.node_type == 'masternode' or args.node_type == 'delegate', \
        'Provide node type as "masternode" or "delegate"'

    sk = bytes.fromhex(args.key)

    wallet = Wallet(seed=sk)

    # REMOVED FOR LAMDEN 2.0. The constitution will be taken from a bootnode directly using ZMQ
    mn_seed = f'tcp://{args.mn_seed}:19000'

    mn_id_response = requests.get(f'http://{args.mn_seed}:{args.mn_seed_port}/id')

    bootnodes = {mn_id_response.json()['verifying_key']: mn_seed}

    ip_str = requests.get('http://api.ipify.org').text
    socket_base = f'tcp://{ip_str}:19000'

    # Setup Environment
    CURR_DIR = pathlib.Path(os.getcwd())
    os.environ['PKG_ROOT'] = str(CURR_DIR.parent)
    os.environ['CIL_PATH'] = os.environ.get('PKG_ROOT') + '/lamden'

    if args.node_type == 'masternode':
        cfg_and_start_rsync_daemon()

        n = Masternode(
            wallet=wallet,
            socket_base=socket_base,
            constitution={},
            webserver_port=args.webserver_port,
            bootnodes=bootnodes,
            seed=mn_seed,
            node_type=args.node_type
        )
    elif args.node_type == 'delegate':
        n = Delegate(
            wallet=wallet,
            socket_base=socket_base,
            constitution={},
            bootnodes=bootnodes,
            seed=mn_seed,
            node_type=args.node_type
        )

    loop = asyncio.get_event_loop()
    asyncio.async(n.start())
    loop.run_forever()
