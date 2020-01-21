import argparse


# class HandleUpdate(argparse.Action):
#     def upd_trigger():
#         pass
#
#     def upd_vote():
#         pass
#
#     def upd_ready():
#         pass

parser = argparse.ArgumentParser(description = "Lamden Commands", prog='cil')

# create parser for update commands
subparser = parser.add_subparsers(title = 'subcommands', description='Network update commands',
                                  help = 'Shows set of update cmd options')

upd_parser = subparser.add_parser('update')

upd_parser.add_argument('--trigger', dest = 'hash', nargs = '?',
                        help='Notify network of new update available')

upd_parser.parse_args('--trigger'.split())

# upd_parser.add_argument('-v', '--vote', action = 'store_true', default = False,
#                         help='Register consent for network version upgrade')
#
# upd_parser.add_argument('-r', '--ready', action = 'store_true', default = False,
#                         help='Notify network for update readiness')


# create parser for view commands

# create parser for node admin commands


# create parser for stats commands

# create parser for debug/logging view

#parser.print_help()

args = parser.parse_args()


print(args)