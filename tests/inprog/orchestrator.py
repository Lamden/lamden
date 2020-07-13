import os
from contracting.db.encoder import encode, decode
from cilantro_ee.crypto.wallet import Wallet
import asyncio
from copy import deepcopy
from contracting.db.driver import ContractDriver, InMemDriver, Driver
from cilantro_ee.nodes.delegate.delegate import Delegate
from cilantro_ee.nodes.masternode.masternode import Masternode

from cilantro_ee.crypto.transaction import build_transaction
from contracting import config

from contracting.stdlib.bridge.decimal import ContractingDecimal
from collections import defaultdict
import random


import aiohttp


def make_ipc(p):
    try:
        os.mkdir(p)
    except:
        pass


def make_network(masternodes, delegates, ctx):
    mn_wallets = [Wallet() for _ in range(masternodes)]
    dl_wallets = [Wallet() for _ in range(delegates)]

    constitution = {
        'masternodes': [mn.verifying_key for mn in mn_wallets],
        'delegates': [dl.verifying_key for dl in dl_wallets],
    }

    mns = []
    dls = []

    bootnodes = {}

    for i in range(len(mn_wallets + dl_wallets)):
        port = 18000 + i
        tcp = f'tcp://127.0.0.1:{port}'

        vk = (mn_wallets + dl_wallets)[i]
        bootnodes[vk.verifying_key] = tcp

    node_count = 0
    for wallet in mn_wallets:
        driver = ContractDriver(driver=Driver(collection=wallet.verifying_key))
        # driver = IsolatedDriver()
        port = 18000 + node_count
        tcp = f'tcp://127.0.0.1:{port}'

        mn = Masternode(
            wallet=wallet,
            ctx=ctx,
            socket_base=tcp,
            bootnodes=bootnodes,
            constitution=deepcopy(constitution),
            webserver_port=18080 + node_count,
            driver=driver,
        )

        mns.append(mn)
        node_count += 1

    for wallet in dl_wallets:
        driver = ContractDriver(driver=Driver(collection=wallet.verifying_key))
        # driver = IsolatedDriver()
        port = 18000 + node_count
        tcp = f'tcp://127.0.0.1:{port}'

        dl = Delegate(
            wallet=wallet,
            ctx=ctx,
            socket_base=tcp,
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
    batch = build_transaction(
        wallet=sender,
        contract=contract_name,
        function=function_name,
        kwargs=kwargs,
        stamps=stamps,
        processor=processor,
        nonce=nonce
    )

    currency_contract = 'currency'
    balances_hash = 'balances'

    balances_key = '{}{}{}{}{}'.format(currency_contract,
                                       config.INDEX_SEPARATOR,
                                       balances_hash,
                                       config.DELIMITER,
                                       sender.verifying_key)

    for driver in drivers:
        driver.set(balances_key, 1_000_000)
        driver.commit()

    return batch


async def send_tx(masternode: Masternode, nodes, contract, function, sender=Wallet(), kwargs={}, sleep=2):
    async with aiohttp.ClientSession() as session:
        r = await session.post(
            url=f'http://127.0.0.1:{masternode.webserver.port}/',
            data=make_tx_packed(
                masternode.wallet.verifying_key,
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


async def send_tx_batch(masternode, txs, server='http://127.0.0.1'):
    hashes = []
    async with aiohttp.ClientSession() as session:
        for tx in txs:
            res = await session.post(
                url=f'{server}:{masternode.webserver.port}/',
                data=tx
            )
            # hashes.append(res)

    return hashes


class Orchestrator:
    def __init__(self, masternode_num, delegate_num, ctx):
        self.ctx = ctx
        mns, dels = make_network(masternode_num, delegate_num, ctx)
        self.masternodes = mns
        self.delegates = dels
        self.nodes = self.masternodes + self.delegates

        self.start_network = make_start_awaitable(self.masternodes, self.delegates)

        self.nonces = defaultdict(int)
        self.minted = set()

    def reset(self):
        self.nonces.clear()
        self.minted.clear()

    def make_tx(self, contract, function, sender, kwargs={}, stamps=1_000_000, pidx=0):
        processor = self.masternodes[pidx]

        batch = build_transaction(
            wallet=sender,
            contract=contract,
            function=function,
            kwargs=kwargs,
            stamps=stamps,
            processor=processor.wallet.verifying_key,
            nonce=self.nonces[sender.verifying_key + processor.wallet.verifying_key]
        )

        self.nonces[sender.verifying_key + processor.wallet.verifying_key] += 1

        if sender.verifying_key not in self.minted:
            self.mint(1_000_000, sender)

        return batch

    def mint(self, amount, to):
        currency_contract = 'currency'
        balances_hash = 'balances'

        balances_key = '{}{}{}{}{}'.format(currency_contract,
                                           config.INDEX_SEPARATOR,
                                           balances_hash,
                                           config.DELIMITER,
                                           to.verifying_key)

        for driver in [node.driver for node in self.nodes]:
            driver.set(balances_key, amount)
            driver.commit()

        self.minted.add(to.verifying_key)

    def get_var(self, contract, function, arguments=[]):
        vals = []
        # Masternodes are always 1 block ahead of delegates in state if the system is halted because of no work.
        # When there is work, they send the NBN, which has the T+1 state deltas, to dels. and the new work.
        for node in self.masternodes:
            v = node.driver.get_var(
                contract=contract,
                variable=function,
                arguments=arguments)

            vals.append(v)

        if len(vals) > 1:
            for v in vals:
                assert vals[0] == v, 'Consensus failure'

        return vals.pop()

    # get value from all driver