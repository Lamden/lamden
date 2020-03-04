import argparse
from cilantro_ee.cli.utils import validate_ip
from cilantro_ee.cli.start import start_node, setup_node, join_network
from cilantro_ee.cli.update import verify_access, verify_pkg, trigger, vote, check_ready_quorum
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

    upd_parser.add_argument('-c', '--check', action = 'store_true', default = False,
                            help='Bool : check current state of network')

    upd_parser.add_argument('-i, ''--ip', type=str, help='Master Node TX End points',
                            required=True)

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

        print(args)
        ip = validate_ip(address=args.ip)

        if args.pkg_hash:
            result = verify_pkg(args.pkg_hash)
            if result is True:
                print('Cilantro has same version running')
            else:
                trigger(pkg=args.pkg_hash, iaddr=ip)

        if args.vote:
            vote(iaddr=args.ip)

        if args.check:
            check_ready_quorum(iaddr=args.ip)


if __name__ == '__main__':
    main()
