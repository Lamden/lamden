import argparse
from cilantro.crypto.transaction import TransactionBuilder
from cilantro.crypto.wallet import Wallet



class Cilparser:
    def __init__(self):
        self.pkg = args.pkg_hash
        self.vote = args.vote
        self.ready = args.ready

        print(self.pkg, self.vote, self.ready)

    def trigger(self, sk=None):
        my_wallet = Wallet(seed=sk)
        pepper = 'RAMDOM' # TODO replace with verified pepper pkg
        kwargs = {'pepper': pepper,'vk': my_wallet.verifying_key}
        vk = my_wallet.verifying_key

        #TODO bail out if vk is not in list of master nodes

        pack = TransactionBuilder(
            sender=vk,
            contract='upgrade',
            function='trigger_upgrade',
            kwargs=kwargs,
            stamps=1_000_000,
            processor=vk,
            nonce=0
        )

        pack.sign(my_wallet.signing_key)
        m = pack.serialize()

        return m

    def vote(self, sk=None):
        my_wallet = Wallet(seed=sk)
        kwargs = {'vk': my_wallet.verifying_key}

        pack = TransactionBuilder(
            sender=my_wallet.verifying_key,
            contract='upgrade',
            function='vote',
            kwargs=kwargs,
            stamps=1_000_000,
            processor=my_wallet.verifying_key,
            nonce=0
        )

        pack.sign(my_wallet.signing_key)
        m = pack.serialize()

        return m

    def check_ready_quorum(self, sk=None):
        my_wallet = Wallet(seed=sk)
        kwargs = {'vk': my_wallet.verifying_key}

        pack = TransactionBuilder(
            sender=my_wallet.verifying_key,
            contract='upgrade',
            function='check_vote_state',
            kwargs=kwargs,
            stamps=1_000_000,
            processor=my_wallet.verifying_key,
            nonce=0
        )

        pack.sign(my_wallet.signing_key)
        m = pack.serialize()

        return m

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

    shell = Cilparser()

    if args.pkg_hash:
        shell.trigger(sk='ad2c4ef0ef8c271fdfc948d5925f3d9313cce6910c137b469a7667461da10e7d')
        # execute upgrade contract

    if args.vote:
        res = shell.vote(sk='ad2c4ef0ef8c271fdfc948d5925f3d9313cce6910c137b469a7667461da10e7d')

    if args.ready:
        print(args)
        res = shell.check_ready_quorum(sk='ad2c4ef0ef8c271fdfc948d5925f3d9313cce6910c137b469a7667461da10e7d')