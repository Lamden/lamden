from lamden.crypto.wallet import Wallet
from lamden.crypto.transaction import build_transaction
import requests
import secrets
import time
import random
import asyncio

class TransactionMaker:
    def __init__(self, server, controller_wallet: Wallet, alternative_servers=None, stamp_default=500_000):
        self.server = server
        self.alternative_servers = alternative_servers

        if self.alternative_servers is not None:
            self.alternative_servers.append(self.server)

        self.controller_wallet = controller_wallet

        self.stamp_default = stamp_default

    def _get_server(self):
        if self.alternative_servers is None:
            return self.server
        else:
            return random.choice(self.alternative_servers)

    def send_tx(self, sender: Wallet, contract: str, function: str, kwargs: dict = {}, stamps: int = 500_000):
        server = self._get_server()

        nonce_req = requests.get('{}/nonce/{}'.format(server, sender.verifying_key))
        nonce = nonce_req.json()['nonce']
        processor = nonce_req.json()['processor']

        tx = build_transaction(
            wallet=sender,
            processor=processor,
            stamps=stamps,
            nonce=nonce,
            contract=contract,
            function=function,
            kwargs=kwargs
        )

        return requests.post(server, data=tx, verify=False)

    def fund(self, verifying_key, amount=250_000):
        self.send_tx(self.controller_wallet, 'currency', 'transfer',
                {
                    'amount': amount,
                    'to': verifying_key
                })


class UpgradeTransactionMaker(TransactionMaker):
    def __init__(self, masternodes, delegates, wait=2, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.masternodes = masternodes
        self.delegates = delegates

        self.wait = wait

        self.is_setup = False

    async def setup(self):
        for node in self.masternodes + self.delegates:
            self.fund(node.verifying_key)
            await asyncio.sleep(self.wait)

        self.is_setup = True

    def initiate_upgrade(self, cilantro_branch_name, contracting_branch_name, pepper):
        self.send_tx(self.masternodes[0], 'upgrade', 'vote',
                {
                    'cilantro_branch_name': cilantro_branch_name,
                    'contracting_branch_name': contracting_branch_name,
                    'pepper': pepper
                })

    async def vote_for_upgrade(self):
        nodes = (self.masternodes + self.delegates)[1:]
        for node in nodes:
            self.send_tx(node, 'upgrade', 'vote')
            await asyncio.sleep(self.wait)
