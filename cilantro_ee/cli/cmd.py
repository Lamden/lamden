import argparse
from cilantro_ee.cli.start import start_node, setup_node, join_network
from cilantro_ee.cil.update import verify_access, verify_pkg
from cilantro_ee.storage import MasterStorage, BlockchainDriver


def flush(args):
    if args.storage_type == 'blocks':
        MasterStorage().drop_collections()
        print('All blocks deleted.')
    elif args.storage_type == 'state':
        BlockchainDriver().flush()
        print('State deleted.')
    elif args.storage_type == 'all':
        MasterStorage().drop_collections()
        BlockchainDriver().flush()
        print('All blocks deleted.')
        print('State deleted.')
    else:
        print('Invalid option. < blocks | state | all >')


def setup_cilparser(parser):
    # create parser for update commands
    subparser = parser.add_subparsers(title = 'subcommands', description='Network update commands',
                                      help = 'Shows set of update cmd options', dest='command')

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

    flush_parser = subparser.add_parser('flush')
    flush_parser.add_argument('storage_type', type=str)

    setup_parser = subparser.add_parser('setup')

    join_parser = subparser.add_parser('join')
    join_parser.add_argument('node_type', type=str)
    join_parser.add_argument('-k', '--key', type=str)
    join_parser.add_argument('-m', '--mn_seed', type=str)
    join_parser.add_argument('-c', '--constitution', type=str, default='~/constitution.json')
    join_parser.add_argument('-wp', '--webserver_port', type=int, default=18080)

    # create parser for view commands
        #TODO
    # create parser for node admin commands
        #TODO
    # create parser for stats commands
        #TODO
    # create parser for debug/logging view
        #TODO
    return True


def main():
    parser = argparse.ArgumentParser(description="Lamden Commands", prog='cil')
    setup_cilparser(parser)
    args = parser.parse_args()

    # implementation
    if vars(args).get('command') is None:
        print('Howdy.︎')
        return

    if args.command == 'start':
        start_node(args)

    elif args.command == 'setup':
        setup_node()

    elif args.command == 'flush':
        flush(args)

    elif args.command == 'join':
        join_network(args)

    elif args.command == 'update':

        my_wallet = verify_access()
        if args.pkg_hash:
            result = verify_pkg(args.pkg_hash)
            if result is True:
                print('Cilantro has same version running')
            else:
                vk = my_wallet.verifying_key()


        if args.vote:
            #shell.vote(sk='ad2c4ef0ef8c271fdfc948d5925f3d9313cce6910c137b469a7667461da10e7d')
            pass

        if args.ready:
            pass


if __name__ == '__main__':
    main()
