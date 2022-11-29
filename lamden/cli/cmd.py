from contracting.client import ContractDriver, ContractingClient
from lamden.cli.start import start_node, join_network
from lamden.contracts import sync
from lamden.storage import BlockStorage
import argparse

def flush(args):
    if args.storage_type == 'blocks':
        BlockStorage().flush()
    elif args.storage_type == 'state':
        ContractDriver().flush()
    elif args.storage_type == 'all':
        BlockStorage().flush()
        ContractDriver().flush()
    else:
        print('Invalid option. < blocks | state | all >')

def setup_cilparser(parser):
    # create parser for update commands
    subparser = parser.add_subparsers(title='subcommands', description='Network update commands',
                                      help='Shows set of update cmd options', dest='command')

    start_parser = subparser.add_parser('start')
    start_parser.add_argument('-c', '--constitution', type=str, default='~/constitution.json')
    start_parser.add_argument('-gb', '--genesis_block', type=str, default='~/genesis_block.json')
    start_parser.add_argument('-wp', '--webserver_port', type=int, default=18080)
    start_parser.add_argument('-p', '--pid', type=int, default=-1)
    start_parser.add_argument('-b', '--bypass_catchup', type=bool, default=False)
    start_parser.add_argument('-d', '--debug', type=bool, default=False)

    flush_parser = subparser.add_parser('flush')
    flush_parser.add_argument('storage_type', type=str)

    join_parser = subparser.add_parser('join')
    join_parser.add_argument('-m', '--mn_seed', type=str)
    join_parser.add_argument('-mp', '--mn_seed_port', type=int, default=18080)
    join_parser.add_argument('-wp', '--webserver_port', type=int, default=18080)

    sync_parser = subparser.add_parser('sync')

    return True

def main():
    parser = argparse.ArgumentParser(description="Lamden Commands", prog='lamden')
    setup_cilparser(parser)
    args = parser.parse_args()

    # implementation
    if vars(args).get('command') is None:
        return

    if args.command == 'start':
        start_node(args)

    elif args.command == 'flush':
        flush(args)

    elif args.command == 'join':
        join_network(args)

    elif args.command == 'sync':
        client = ContractingClient()
        sync.flush_sys_contracts(client=client)
        sync.submit_from_genesis_json_file(client=client)

if __name__ == '__main__':
    main()
