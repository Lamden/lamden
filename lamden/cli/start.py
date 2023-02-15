import requests
import pathlib
import json
import os
import asyncio
import subprocess
from subprocess import call

from lamden.crypto.wallet import Wallet
from lamden.nodes.base import Node
from lamden.logger.base import get_logger

from contracting.db.encoder import decode


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

def start_node(args):
    logger = get_logger('STARTUP')

    sk = bytes.fromhex(os.environ['LAMDEN_SK'])

    wallet = Wallet(seed=sk)

    logger.info({'node vk': wallet.verifying_key})

    bootnodes = resolve_constitution(args.constitution)
    genesis_block = resolve_genesis_block(args.genesis_block)

    logger.info({'bootnodes': bootnodes})

    assert len(bootnodes) > 0, 'Must provide at least one bootnode.'

    ip_str = requests.get('http://api.ipify.org').text
    socket_base = f'tcp://{ip_str}:19000'

    logger.info(f'socket_base: {socket_base}')

    # Kill the
    if args.pid > -1:
        subprocess.check_call(['kill', '-15', str(args.pid)])

    n = Node(
        debug=args.debug,
        wallet=wallet,
        socket_base=socket_base,
        bootnodes=bootnodes,
        bypass_catchup=args.bypass_catchup,
        genesis_block=genesis_block,
        metering=True
    )

    loop = asyncio.get_event_loop()
    asyncio.ensure_future(n.start())
    loop.run_forever()


def join_network(args):
    sk = bytes.fromhex(os.environ['LAMDEN_SK'])

    wallet = Wallet(seed=sk)

    bootnode_ips = os.environ['LAMDEN_BOOTNODES'].split(':')
    bootnodes = {}
    for ip in bootnode_ips:
        resp = requests.get(f'http://{ip}:18080/id').json()
        vk = resp.get('verifying_key') 
        if vk is not None:
            bootnodes[vk] = f'tcp://{ip}:19000'

    ip_str = requests.get('http://api.ipify.org').text
    socket_base = f'tcp://{ip_str}:19000'

    n = Node(
        debug=args.debug,
        wallet=wallet,
        socket_base=socket_base,
        bootnodes=bootnodes,
        join=True,
        metering=True
    )

    loop = asyncio.get_event_loop()
    asyncio.ensure_future(n.start())
    loop.run_forever()
