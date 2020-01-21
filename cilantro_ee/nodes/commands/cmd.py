import argparse

parser = argparse.ArgumentParser(description = "Lamden Commands", prog='cil')

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


# create parser for view commands

# create parser for node admin commands


# create parser for stats commands

# create parser for debug/logging view


args = parser.parse_args()

#print(args)

# implementation

if args.pkg_hash:
    print(args.pkg_hash)
    # execute upgrade contract

if args.vote:
    print(args.vote)

if args.ready:
    print(args.ready)