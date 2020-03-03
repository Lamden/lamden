import aiohttp
import asyncio
from getpass import getpass
from cilantro_ee.crypto.wallet import Wallet
from cilantro_ee.crypto.transaction import TransactionBuilder
from scripts.pkg import verify_pkg


async def cil_interface(mn, packed_data, sleep=2):
    async with aiohttp.ClientSession() as session:
        r = await session.post(
            url=f'http://127.0.0.1:{mn.webserver.port}/',
            data=packed_data
        )

        result = await r.json()
        await asyncio.sleep(sleep)
        return result


def verify_access():
    while True:
        sk = getpass('Signing Key in Hex Format: ')

        try:
            wallet = Wallet(seed=bytes.fromhex(sk))
            return wallet
        except:
            print('Invalid format! Try again.')


def trigger(pkg=None):

    my_wallet = verify_access()
    pepper = pkg  #TODO replace with verified pepper pkg
    kwargs = {'pepper': pepper, 'vk': my_wallet.verifying_key()}
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
    print(m)


def vote():
    my_wallet = verify_access()
    pkg_check = verify_pkg()

    if pkg_check is False:
        print('Invalid package hash does not match')
        return

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

    print(m)


def check_ready_quorum():
    my_wallet = verify_access()
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
    print(m)
