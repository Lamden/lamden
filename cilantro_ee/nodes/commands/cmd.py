import argparse
import requests
import pathlib
import json
import os
import asyncio

import zmq.asyncio

from subprocess import call
from cilantro_ee.crypto.wallet import Wallet
from cilantro_ee.nodes.masternode.masternode import Masternode
from cilantro_ee.nodes.delegate.delegate import Delegate


class Cilparser:
    def __init__(self):
        self.pkg = args.pkg_hash
        self.vote = args.vote
        self.ready = args.ready

        print(self.pkg, self.vote, self.ready)

    def trigger(self, vk=None):
        print('pkg ->', self.pkg)
        return True

    def vote(self, vk=None):
        print('vote ->', vk)
        return True

    def check_ready_quorum(self, vk=None):
        print('ready ->', vk)
        return True


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
    assert 'masternode_min_quorum' in j.keys(), 'No masternode_min_quorum section.'
    assert 'delegates' in j.keys(), 'No delegates section.'
    assert 'delegate_min_quorum' in j.keys(), 'No delegate_min_quorum section.'

    return j


def start_node(args):
    assert args.node_type == 'masternode' or args.node_type == 'delegate', 'Provide node type as "masternode" or "delegate"'

    sk = bytes.fromhex(args.key)

    wallet = Wallet(seed=sk)

    bootnodes = []

    for node in args.boot_nodes:
        assert is_valid_ip(node), 'Invalid IP string provided to boot node argument.'
        bootnodes.append(f'tcp://{node}')

    assert len(bootnodes) > 0, 'Must provide at least one bootnode.'

    const = resolve_constitution(args.constitution)

    ip_str = requests.get('http://api.ipify.org').text
    socket_base = f'tcp://{ip_str}'

    if args.node_type == 'masternode':
        n = Masternode(
            wallet=wallet,
            ctx=zmq.asyncio.Context(),
            socket_base=socket_base,
            bootnodes=bootnodes,
            constitution=const,
            webserver_port=args.webserver_port,
        )
    elif args.node_type == 'delegate':
        n = Delegate(
            wallet=wallet,
            ctx=zmq.asyncio.Context(),
            socket_base=socket_base,
            bootnodes=bootnodes,
            constitution=const,
        )

    loop = asyncio.get_event_loop()
    loop.run_until_complete(n.start())


def setup_cilparser(parser):
    # create parser for update commands
    subparser = parser.add_subparsers(title = 'subcommands', description='Network update commands',
                                      help = 'Shows set of update cmd options')

    upd_parser = subparser.add_parser('update')

    upd_parser.add_argument('-t', '--trigger', dest = 'pkg_hash', nargs = '?', type =str,
                            help='str: Notify network of new update with given pkg_hash')

    upd_parser.parse_args('--trigger'.split())

    upd_parser.add_argument('-v', '--vote', action = 'store_true', default = False,
                            help='Bool : Register consent for network version upgrade')

    upd_parser.add_argument('-r', '--ready', action = 'store_true', default = False,
                            help='Bool : Notify network upgrade ready')

    start_parser = subparser.add_parser('start')

    start_parser.add_argument('node_type', type=str)
    start_parser.add_argument('-k', '--key', type=str)
    start_parser.add_argument('-bn', '--boot-nodes', type=str, nargs='+')
    start_parser.add_argument('-c', '--constitution', type=str, default='~/constitution.json')
    start_parser.add_argument('-wp', '--webserver_port', type=int, default=18080)

    # create parser for view commands
        #TODO
    # create parser for node admin commands
        #TODO
    # create parser for stats commands
        #TODO
    # create parser for debug/logging view
        #TODO
    return True


if __name__ == '__main__':

    parser = argparse.ArgumentParser(description = "Lamden Commands", prog='cil')
    setup_cilparser(parser)
    args = parser.parse_args()

    # implementation

    start_node(args)

    # shell = Cilparser()
    #
    # if args.pkg_hash:
    #     shell.trigger(vk='asdfadf')
    #     # execute upgrade contract
    #
    # if args.vote:
    #     res = shell.vote(vk='asdfadf')
    #
    # if args.ready:
    #     print(args)
    #     res = shell.check_ready_quorum(vk='sdfafda')