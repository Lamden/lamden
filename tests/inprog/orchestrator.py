import os
from contracting.db.encoder import encode, decode
from cilantro_ee.crypto.wallet import Wallet
import asyncio
from copy import deepcopy
from contracting.db.driver import ContractDriver, InMemDriver
from cilantro_ee.nodes.delegate.delegate import Delegate
from cilantro_ee.nodes.masternode.masternode import Masternode

from cilantro_ee.storage import BlockchainDriver
from cilantro_ee.crypto.transaction import TransactionBuilder
from contracting import config

from cilantro_ee.messages.capnp_impl import capnp_struct as schemas
from contracting.stdlib.bridge.decimal import ContractingDecimal
import capnp
from collections import defaultdict
import random

transaction_capnp = capnp.load(os.path.dirname(schemas.__file__) + '/transaction.capnp')

import aiohttp


def make_ipc(p):
    try:
        os.mkdir(p)
    except:
        pass


def make_network(masternodes, delegates, ctx, mn_min_quorum=2, del_min_quorum=2):
    mn_wallets = [Wallet() for _ in range(masternodes)]
    dl_wallets = [Wallet() for _ in range(delegates)]

    constitution = {
        'masternodes': [mn.verifying_key().hex() for mn in mn_wallets],
        'delegates': [dl.verifying_key().hex() for dl in dl_wallets],
        'witnesses': [],
        'schedulers': [],
        'notifiers': [],
        'enable_stamps': False,
        'enable_nonces': False,
        'masternode_min_quorum': mn_min_quorum,
        'delegate_min_quorum': del_min_quorum,
        'witness_min_quorum': 0,
        'notifier_min_quorum': 0,
        'scheduler_min_quorum': 0
    }

    mns = []
    dls = []
    bootnodes = None
    node_count = 0
    for wallet in mn_wallets:
        driver = BlockchainDriver(driver=InMemDriver())
        # driver = IsolatedDriver()
        ipc = f'/tmp/n{node_count}'
        make_ipc(ipc)

        if bootnodes is None:
            bootnodes = [f'ipc://{ipc}']

        mn = Masternode(
            wallet=wallet,
            ctx=ctx,
            socket_base=f'ipc://{ipc}',
            bootnodes=bootnodes,
            constitution=deepcopy(constitution),
            webserver_port=18080 + node_count,
            driver=driver
        )

        mns.append(mn)
        node_count += 1

    for wallet in dl_wallets:
        driver = BlockchainDriver(driver=InMemDriver())
        # driver = IsolatedDriver()
        ipc = f'/tmp/n{node_count}'
        make_ipc(ipc)

        dl = Delegate(
            wallet=wallet,
            ctx=ctx,
            socket_base=f'ipc://{ipc}',
            constitution=deepcopy(constitution),
            bootnodes=bootnodes,
            driver=driver
        )

        dls.append(dl)
        node_count += 1

    return mns, dls


def make_start_awaitable(mns, dls):
    coros = []
    for mn in mns:
        coros.append(mn.start())

    for dl in dls:
        coros.append(dl.start())

    return asyncio.gather(*coros)


def make_tx_packed(processor, contract_name, function_name, sender=Wallet(), kwargs={}, drivers=[], stamps=10_000, nonce=0):
    batch = TransactionBuilder(
        sender=sender.verifying_key(),
        contract=contract_name,
        function=function_name,
        kwargs=kwargs,
        stamps=stamps,
        processor=processor,
        nonce=nonce
    )

    batch.sign(sender.signing_key())
    b = batch.serialize()

    currency_contract = 'currency'
    balances_hash = 'balances'

    balances_key = '{}{}{}{}{}'.format(currency_contract,
                                       config.INDEX_SEPARATOR,
                                       balances_hash,
                                       config.DELIMITER,
                                       sender.verifying_key().hex())

    for driver in drivers:
        driver.set(balances_key, 1_000_000)
        driver.commit()

    return b


async def send_tx(masternode: Masternode, nodes, contract, function, sender=Wallet(), kwargs={}, sleep=2):
    async with aiohttp.ClientSession() as session:
        r = await session.post(
            url=f'http://127.0.0.1:{masternode.webserver.port}/',
            data=make_tx_packed(
                masternode.wallet.verifying_key(),
                contract_name=contract,
                function_name=function,
                sender=sender,
                kwargs=kwargs,
                drivers=[node.driver for node in nodes],
                nonce=0
            )
        )

    res = await r.json()
    await asyncio.sleep(sleep)
    return res


async def send_tx_batch(masternode, txs):
    async with aiohttp.ClientSession() as session:
        for tx in txs:
            await session.post(
                url=f'http://127.0.0.1:{masternode.webserver.port}/',
                data=tx
            )


class Orchestrator:
    def __init__(self, masternode_num, delegate_num, ctx, min_mn_quorum=2, min_del_quorum=2):
        self.ctx = ctx
        mns, dels = make_network(masternode_num, delegate_num, ctx, min_mn_quorum, min_del_quorum)
        self.masternodes = mns
        self.delegates = dels
        self.nodes = self.masternodes + self.delegates

        self.start_network = make_start_awaitable(self.masternodes, self.delegates)

        self.nonces = defaultdict(int)
        self.minted = set()

    def reset(self):
        self.nonces.clear()
        self.minted.clear()

    def make_tx(self, contract, function, sender, kwargs={}, stamps=1_000_000):
        processor = self.masternodes[0]

        batch = TransactionBuilder(
            sender=sender.verifying_key(),
            contract=contract,
            function=function,
            kwargs=kwargs,
            stamps=stamps,
            processor=processor.wallet.verifying_key(),
            nonce=self.nonces[sender.verifying_key() + processor.wallet.verifying_key()]
        )

        batch.sign(sender.signing_key())
        b = batch.serialize()

        self.nonces[sender.verifying_key() + processor.wallet.verifying_key()] += 1

        if sender.verifying_key() not in self.minted:
            self.mint(1_000_000, sender)

        return b

    def mint(self, amount, to):
        currency_contract = 'currency'
        balances_hash = 'balances'

        balances_key = '{}{}{}{}{}'.format(currency_contract,
                                           config.INDEX_SEPARATOR,
                                           balances_hash,
                                           config.DELIMITER,
                                           to.verifying_key().hex())

        for driver in [node.driver for node in self.nodes]:
            driver.set(balances_key, amount)

        self.minted.add(to.verifying_key())

    # get value from all driver