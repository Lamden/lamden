import aiohttp
import asyncio
import requests
from getpass import getpass
from cilantro_ee.nodes.base import Node
from cilantro_ee.crypto.wallet import Wallet
from cilantro_ee.crypto.transaction import TransactionBuilder
from cilantro_ee.cli.utils import get_update_state
from scripts.pkg import verify_pkg


async def cil_interface(server, packed_data, sleep=2):
    async with aiohttp.ClientSession() as session:
        r = await session.post(
            url=f'http://{server}:18080/',
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
            print('Access validated')
            return wallet
        except:
            print('Invalid format! Try again.')


def trigger(pkg=None, iaddr=None):

    my_wallet = verify_access()
    pepper = pkg  #TODO replace with verified pepper pkg
    kwargs = {'pepper': pepper, 'initiator_vk': my_wallet.verifying_key().hex()}
    vk = my_wallet.verifying_key()

    SERVER = f'http://{iaddr}:18080'

    nonce_req = requests.get('{}/nonce/{}'.format(SERVER, my_wallet.verifying_key().hex()))
    nonce = nonce_req.json()['nonce']

    #TODO bail out if vk is not in list of master nodes

    pack = TransactionBuilder(
        sender=vk,
        contract='upgrade',
        function='trigger_upgrade',
        kwargs=kwargs,
        stamps=100_000,
        processor=vk,
        nonce=nonce
    )

    pack.sign(my_wallet.signing_key())
    m = pack.serialize()
    loop = asyncio.get_event_loop()
    loop.run_until_complete(cil_interface(server=iaddr, packed_data=m, sleep=2))


def vote(iaddr):
    my_wallet = verify_access()
    # pkg_check = verify_pkg()
    #
    # if pkg_check is False:
    #     print('Invalid package hash does not match')
    #     return

    SERVER = f'http://{iaddr}:18080'

    nonce_req = requests.get('{}/nonce/{}'.format(SERVER, my_wallet.verifying_key().hex()))
    nonce = nonce_req.json()['nonce']

    kwargs = {'vk': my_wallet.verifying_key().hex()}

    pack = TransactionBuilder(
        sender=my_wallet.verifying_key(),
        contract='upgrade',
        function='vote',
        kwargs=kwargs,
        stamps=100_000,
        processor=my_wallet.verifying_key(),
        nonce=nonce
    )

    pack.sign(my_wallet.signing_key())
    m = pack.serialize()

    loop = asyncio.get_event_loop()
    loop.run_until_complete(cil_interface(server=iaddr, packed_data=m, sleep=2))


def check_ready_quorum(iaddr):
    get_update_state()


    # my_wallet = verify_access()
    #
    # SERVER = f'http://{iaddr}:18080'
    #
    # nonce_req = requests.get('{}/nonce/{}'.format(SERVER, my_wallet.verifying_key().hex()))
    # nonce = nonce_req.json()['nonce']
    #
    # kwargs = {'vk': my_wallet.verifying_key().hex()}
    #
    # pack = TransactionBuilder(
    #     sender=my_wallet.verifying_key(),
    #     contract='upgrade',
    #     function='check_vote_state',
    #     kwargs=kwargs,
    #     stamps=100_000,
    #     processor=my_wallet.verifying_key(),
    #     nonce=nonce
    # )
    #
    # pack.sign(my_wallet.signing_key())
    # m = pack.serialize()
    # loop = asyncio.get_event_loop()
    # loop.run_until_complete(cil_interface(server=iaddr, packed_data=m, sleep=2))
