from cilantro_ee.nodes.masternode.masternode import NewMasternode
from unittest import TestCase
from cilantro_ee.networking.discovery import *
import zmq
import zmq.asyncio
from cilantro_ee.crypto.wallet import Wallet
import zmq.asyncio
import asyncio
from cilantro_ee.networking.network import Network
from contracting.client import ContractingClient
from cilantro_ee.nodes.work_inbox import WorkInbox
from cilantro_ee.nodes.new_block_inbox import NBNInbox
from cilantro_ee.sockets.services import _socket
from cilantro_ee.crypto.transaction import TransactionBuilder
from cilantro_ee.storage import MetaDataStorage
from contracting import config
import os
import capnp
from cilantro_ee.messages.capnp_impl import capnp_struct as schemas

transaction_capnp = capnp.load(os.path.dirname(schemas.__file__) + '/transaction.capnp')


async def stop_server(s, timeout):
    await asyncio.sleep(timeout)
    s.stop()


def make_ipc(p):
    try:
        os.mkdir(p)
    except:
        pass


class MockContacts:
    def __init__(self, masters, delegates):
        self.masternodes = masters
        self.delegates = delegates


class TestNewMasternode(TestCase):
    def setUp(self):
        self.ctx = zmq.asyncio.Context()
        self.loop = asyncio.new_event_loop()
        ContractingClient().flush()
        asyncio.set_event_loop(self.loop)

    def tearDown(self):
        self.ctx.destroy()
        self.loop.close()

    def test_network_start(self):
        # 4 nodes
        # 2 bootnodes
        # 2 mns, 2 delegates

        bootnodes = ['ipc:///tmp/n1', 'ipc:///tmp/n3']

        mnw1 = Wallet()
        mnw2 = Wallet()
        masternodes = [mnw1.verifying_key().hex(), mnw2.verifying_key().hex()]

        dw1 = Wallet()
        dw2 = Wallet()
        delegates = [dw1.verifying_key().hex(), dw2.verifying_key().hex()]

        constitution = {
            "masternodes": {
                "vk_list": [
                    mnw1.verifying_key().hex(),
                    mnw2.verifying_key().hex()
                ],
                "min_quorum": 1
            },
            "delegates": {
                "vk_list": [
                    dw1.verifying_key().hex(),
                    dw2.verifying_key().hex()
                ],
                "min_quorum": 1
            },
            "witnesses": {},
            "schedulers": {},
            "notifiers": {},
            "enable_stamps": False,
            "enable_nonces": False
        }

        n1 = '/tmp/n1'
        make_ipc(n1)
        mn1 = NewMasternode(wallet=mnw1, ctx=self.ctx, socket_base=f'ipc://{n1}', bootnodes=bootnodes,
                            constitution=constitution, webserver_port=8080)

        n2 = '/tmp/n2'
        make_ipc(n2)
        mn2 = NewMasternode(wallet=mnw2, ctx=self.ctx, socket_base=f'ipc://{n2}', bootnodes=bootnodes,
                            constitution=constitution, webserver_port=8081)

        n3 = '/tmp/n3'
        make_ipc(n3)
        d1 = Network(wallet=dw1, ctx=self.ctx, socket_base=f'ipc://{n3}',
                     bootnodes=bootnodes, mn_to_find=masternodes, del_to_find=delegates)

        n4 = '/tmp/n4'
        make_ipc(n4)
        d2 = Network(wallet=dw2, ctx=self.ctx, socket_base=f'ipc://{n4}',
                     bootnodes=bootnodes, mn_to_find=masternodes, del_to_find=delegates)


        # should test to see all ready signals are recieved
        tasks = asyncio.gather(
            mn1.start(),
            mn2.start(),
            d1.start(),
            d2.start()
        )

        async def run():
            await tasks
            await asyncio.sleep(5)
            mn1.stop()
            mn2.stop()
            d1.stop()
            d2.stop()

        loop = asyncio.get_event_loop()
        loop.run_until_complete(run())

    def test_send_batch_to_delegates(self):
        bootnodes = ['ipc:///tmp/n2', 'ipc:///tmp/n3']

        mnw1 = Wallet()
        mnw2 = Wallet()

        dw1 = Wallet()
        dw2 = Wallet()
        dw3 = Wallet()
        dw4 = Wallet()

        constitution = {
            "masternodes": {
                "vk_list": [
                    mnw1.verifying_key().hex(),
                    mnw2.verifying_key().hex()
                ],
                "min_quorum": 1
            },
            "delegates": {
                "vk_list": [
                    dw1.verifying_key().hex(),
                    dw2.verifying_key().hex(),
                    dw3.verifying_key().hex(),
                    dw4.verifying_key().hex()
                ],
                "min_quorum": 1
            },
            "witnesses": {},
            "schedulers": {},
            "notifiers": {},
            "enable_stamps": False,
            "enable_nonces": False
        }

        n1 = '/tmp/n1'
        make_ipc(n1)
        mn1 = NewMasternode(wallet=mnw1, ctx=self.ctx, socket_base=f'ipc://{n1}', bootnodes=bootnodes,
                            constitution=constitution, webserver_port=8080, overwrite=True)

        masternodes = [mnw1.verifying_key().hex(), mnw2.verifying_key().hex()]
        delegates = [dw1.verifying_key().hex(), dw2.verifying_key().hex(), dw3.verifying_key().hex(), dw4.verifying_key().hex()]

        contacts = MockContacts(
            masters=masternodes,
            delegates=delegates
        )

        d1 = '/tmp/d1'
        make_ipc(d1)
        wi1 = WorkInbox(socket_id=_socket(f'ipc://{d1}/incoming_work'), ctx=self.ctx, contacts=contacts, verify=False)

        d2 = '/tmp/d2'
        make_ipc(d2)
        wi2 = WorkInbox(socket_id=_socket(f'ipc://{d2}/incoming_work'), ctx=self.ctx, contacts=contacts, verify=False)

        d3 = '/tmp/d3'
        make_ipc(d3)
        wi3 = WorkInbox(socket_id=_socket(f'ipc://{d3}/incoming_work'), ctx=self.ctx, contacts=contacts, verify=False)

        d4 = '/tmp/d4'
        make_ipc(d4)
        wi4 = WorkInbox(socket_id=_socket(f'ipc://{d4}/incoming_work'), ctx=self.ctx, contacts=contacts, verify=False)

        w = Wallet()
        batch = TransactionBuilder(
            sender=w.verifying_key(),
            contract='test',
            function='testing',
            kwargs={},
            stamps=1_000_000,
            processor=mnw1.verifying_key(),
            nonce=0
        )

        batch.sign(w.signing_key())
        b = batch.serialize()

        tx = transaction_capnp.Transaction.from_bytes_packed(b)

        currency_contract = 'currency'
        balances_hash = 'balances'

        balances_key = '{}{}{}{}{}'.format(currency_contract,
                                           config.INDEX_SEPARATOR,
                                           balances_hash,
                                           config.DELIMITER,
                                           w.verifying_key().hex())

        driver = MetaDataStorage()
        driver.set(balances_key, 1_000_000)

        mn1.tx_batcher.queue.append(tx)

        mn1.network.peer_service.table.peers = {
            dw1.verifying_key().hex(): f'ipc://{d1}',
            dw2.verifying_key().hex(): f'ipc://{d2}',
            dw3.verifying_key().hex(): f'ipc://{d3}',
            dw4.verifying_key().hex(): f'ipc://{d4}'
        }

        async def late_send():
            await asyncio.sleep(0.3)
            await mn1.parameters.refresh()
            await mn1.send_batch_to_delegates()

        async def stop():
            await asyncio.sleep(0.5)
            wi1.stop()
            wi2.stop()
            wi3.stop()
            wi4.stop()
            mn1.network.stop()

        tasks = asyncio.gather(
            mn1.network.start(False),
            wi1.serve(),
            wi2.serve(),
            wi3.serve(),
            wi4.serve(),
            late_send(),
            stop()
        )

        self.loop.run_until_complete(tasks)

        self.assertTrue(wi1.work[mnw1.verifying_key().hex()])
        self.assertTrue(wi2.work[mnw1.verifying_key().hex()])
        self.assertTrue(wi3.work[mnw1.verifying_key().hex()])
        self.assertTrue(wi4.work[mnw1.verifying_key().hex()])

    def test_send_nbn_to_everyone(self):
        bootnodes = ['ipc:///tmp/n2', 'ipc:///tmp/n3']

        mnw1 = Wallet()
        mnw2 = Wallet()

        dw1 = Wallet()
        dw2 = Wallet()
        dw3 = Wallet()
        dw4 = Wallet()

        constitution = {
            "masternodes": {
                "vk_list": [
                    mnw1.verifying_key().hex(),
                    mnw2.verifying_key().hex()
                ],
                "min_quorum": 1
            },
            "delegates": {
                "vk_list": [
                    dw1.verifying_key().hex(),
                    dw2.verifying_key().hex(),
                    dw3.verifying_key().hex(),
                    dw4.verifying_key().hex()
                ],
                "min_quorum": 1
            },
            "witnesses": {},
            "schedulers": {},
            "notifiers": {},
            "enable_stamps": False,
            "enable_nonces": False
        }

        n1 = '/tmp/n1'
        make_ipc(n1)
        mn1 = NewMasternode(wallet=mnw1, ctx=self.ctx, socket_base=f'ipc://{n1}', bootnodes=bootnodes,
                            constitution=constitution, webserver_port=8080, overwrite=True)

        masternodes = [mnw1.verifying_key().hex(), mnw2.verifying_key().hex()]
        delegates = [dw1.verifying_key().hex(), dw2.verifying_key().hex(), dw3.verifying_key().hex(),
                     dw4.verifying_key().hex()]

        contacts = MockContacts(
            masters=masternodes,
            delegates=delegates
        )

        d1 = '/tmp/d1'
        make_ipc(d1)
        wi1 = NBNInbox(socket_id=_socket(f'ipc://{d1}/incoming_work'), ctx=self.ctx, contacts=contacts, verify=False)

        d2 = '/tmp/d2'
        make_ipc(d2)
        wi2 = NBNInbox(socket_id=_socket(f'ipc://{d2}/incoming_work'), ctx=self.ctx, contacts=contacts, verify=False)

        d3 = '/tmp/d3'
        make_ipc(d3)
        wi3 = NBNInbox(socket_id=_socket(f'ipc://{d3}/incoming_work'), ctx=self.ctx, contacts=contacts, verify=False)

        d4 = '/tmp/d4'
        make_ipc(d4)
        wi4 = NBNInbox(socket_id=_socket(f'ipc://{d4}/incoming_work'), ctx=self.ctx, contacts=contacts, verify=False)

    def test_send_to_delegates_doesnt_hang_if_one_is_not_online(self):
        bootnodes = ['ipc:///tmp/n2', 'ipc:///tmp/n3']

        mnw1 = Wallet()
        mnw2 = Wallet()

        dw1 = Wallet()
        dw2 = Wallet()
        dw3 = Wallet()
        dw4 = Wallet()

        constitution = {
            "masternodes": {
                "vk_list": [
                    mnw1.verifying_key().hex(),
                    mnw2.verifying_key().hex()
                ],
                "min_quorum": 1
            },
            "delegates": {
                "vk_list": [
                    dw1.verifying_key().hex(),
                    dw2.verifying_key().hex(),
                    dw3.verifying_key().hex(),
                    dw4.verifying_key().hex()
                ],
                "min_quorum": 1
            },
            "witnesses": {},
            "schedulers": {},
            "notifiers": {},
            "enable_stamps": False,
            "enable_nonces": False
        }

        n1 = '/tmp/n1'
        make_ipc(n1)
        mn1 = NewMasternode(wallet=mnw1, ctx=self.ctx, socket_base=f'ipc://{n1}', bootnodes=bootnodes,
                            constitution=constitution, webserver_port=8080, overwrite=True)

        masternodes = [mnw1.verifying_key().hex(), mnw2.verifying_key().hex()]
        delegates = [dw1.verifying_key().hex(), dw2.verifying_key().hex(), dw3.verifying_key().hex(),
                     dw4.verifying_key().hex()]

        contacts = MockContacts(
            masters=masternodes,
            delegates=delegates
        )

        d1 = '/tmp/d1'
        make_ipc(d1)
        wi1 = WorkInbox(socket_id=_socket(f'ipc://{d1}/incoming_work'), ctx=self.ctx, contacts=contacts, verify=False)

        d2 = '/tmp/d2'
        make_ipc(d2)
        wi2 = WorkInbox(socket_id=_socket(f'ipc://{d2}/incoming_work'), ctx=self.ctx, contacts=contacts, verify=False)

        d3 = '/tmp/d3'
        make_ipc(d3)
        #wi3 = WorkInbox(socket_id=_socket(f'ipc://{d3}/incoming_work'), ctx=self.ctx, contacts=contacts, verify=False)

        d4 = '/tmp/d4'
        make_ipc(d4)
        wi4 = WorkInbox(socket_id=_socket(f'ipc://{d4}/incoming_work'), ctx=self.ctx, contacts=contacts, verify=False)

        w = Wallet()
        batch = TransactionBuilder(
            sender=w.verifying_key(),
            contract='test',
            function='testing',
            kwargs={},
            stamps=1_000_000,
            processor=mnw1.verifying_key(),
            nonce=0
        )

        batch.sign(w.signing_key())
        b = batch.serialize()

        tx = transaction_capnp.Transaction.from_bytes_packed(b)

        currency_contract = 'currency'
        balances_hash = 'balances'

        balances_key = '{}{}{}{}{}'.format(currency_contract,
                                           config.INDEX_SEPARATOR,
                                           balances_hash,
                                           config.DELIMITER,
                                           w.verifying_key().hex())

        driver = MetaDataStorage()
        driver.set(balances_key, 1_000_000)

        mn1.tx_batcher.queue.append(tx)

        mn1.network.peer_service.table.peers = {
            dw1.verifying_key().hex(): f'ipc://{d1}',
            dw2.verifying_key().hex(): f'ipc://{d2}',
            dw3.verifying_key().hex(): f'ipc://{d3}',
            dw4.verifying_key().hex(): f'ipc://{d4}'
        }

        async def late_send():
            await asyncio.sleep(0.3)
            await mn1.parameters.refresh()
            return await mn1.send_batch_to_delegates()

        async def stop():
            await asyncio.sleep(0.5)
            wi1.stop()
            wi2.stop()
            wi4.stop()
            mn1.network.stop()

        tasks = asyncio.gather(
            mn1.network.start(False),
            wi1.serve(),
            wi2.serve(),
            wi4.serve(),
            late_send(),
            stop()
        )

        _, _, _, _, r, _ = self.loop.run_until_complete(tasks)

        # Make sure the right socket failed
        for rr in r:
            if not rr[0]:
                self.assertEqual(rr[1], f'ipc://{d3}/incoming_work')

        self.assertTrue(wi1.work[mnw1.verifying_key().hex()])
        self.assertTrue(wi2.work[mnw1.verifying_key().hex()])
        #self.assertTrue(wi3.work[mnw1.verifying_key().hex()])
        self.assertTrue(wi4.work[mnw1.verifying_key().hex()])