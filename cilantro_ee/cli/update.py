from getpass import getpass
from cilantro_ee.crypto.wallet import Wallet
from cilantro_ee.crypto.transaction import TransactionBuilder


def verify_access():
    while True:
        sk = getpass('Signing Key in Hex Format: ')

        try:
            wallet = Wallet(seed=bytes.fromhex(sk))
            return wallet
        except:
            print('Invalid format! Try again.')


def verify_pkg(pkg):
    return True


def trigger(self, vk=None, pkg=None):
    my_wallet = Wallet.from_sk(sk=sk)
    pepper = 'RAMDOM' # TODO replace with verified pepper pkg
    kwargs = {'pepper': pepper,'vk': my_wallet.verifying_key()}
    vk = my_wallet.verifying_key()

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

    pack.sign(my_wallet.signing_key())
    m = pack.serialize()

    return m

def vote(self, vk=None):
    my_wallet = Wallet.from_sk(sk=sk)
    kwargs = {'vk': my_wallet.verifying_key()}

    pack = TransactionBuilder(
        sender=my_wallet.verifying_key(),
        contract='upgrade',
        function='vote',
        kwargs=kwargs,
        stamps=1_000_000,
        processor=my_wallet.verifying_key(),
        nonce=0
    )

    pack.sign(my_wallet.signing_key())
    m = pack.serialize()

    return m

def check_ready_quorum(self, vk=None):
    my_wallet = Wallet.from_sk(sk=sk)
    kwargs = {'vk': my_wallet.verifying_key()}

    pack = TransactionBuilder(
        sender=my_wallet.verifying_key(),
        contract='upgrade',
        function='check_vote_state',
        kwargs=kwargs,
        stamps=1_000_000,
        processor=my_wallet.verifying_key(),
        nonce=0
    )

    pack.sign(my_wallet.signing_key())
    m = pack.serialize()

    return m