import lamden.nodes.masternode.masternode
from lamden.nodes.masternode.masternode import Masternode
from unittest import TestCase
from lamden.networking.discovery import *
import zmq
import zmq.asyncio
from lamden.crypto.wallet import Wallet
import asyncio
from lamden.network import Network
from lamden.crypto import canonical
from contracting.client import ContractingClient
from lamden.nodes.work_inbox import WorkInbox
from lamden.nodes.new_block_inbox import NBNInbox
from lamden.struct import _socket
from lamden.crypto.transaction import TransactionBuilder
from lamden.crypto.transaction_batch import transaction_list_to_transaction_batch
from lamden.storage import StateDriver
from contracting import config
import os
import capnp
from lamden.messages import capnp_struct as schemas
import secrets
from tests import random_txs

transaction_capnp = capnp.load(os.path.dirname(schemas.__file__) + '/transaction.capnp')


def put_test_contract(client):
    test_contract = '''
v = Variable()

@construct
def seed():
    v.set('hello')

@export
def set(var):
    v.set(var)

@export
def get():
    return v.get()
        '''

    client.submit(test_contract, name='testing')


def get_tx_batch():
    w = Wallet()
    tx = TransactionBuilder(
        sender='stu',
        contract='testing',
        function='set',
        kwargs={'var': 'howdy'},
        stamps=100_000,
        processor=b'\x00' * 32,
        nonce=0
    )
    tx.sign(w.signing_key)
    tx.serialize()

    currency_contract = 'currency'
    balances_hash = 'balances'

    balances_key = '{}{}{}{}{}'.format(currency_contract,
                                       config.INDEX_SEPARATOR,
                                       balances_hash,
                                       config.DELIMITER,
                                       w.verifying_key)

    driver = StateDriver()
    driver.set(balances_key, 1_000_000)
    driver.commit()

    w = Wallet()
    tx2 = TransactionBuilder(
        sender='stu',
        contract='testing',
        function='get',
        kwargs={},
        stamps=100_000,
        processor=b'\x00' * 32,
        nonce=0
    )
    tx2.sign(Wallet().signing_key)
    tx2.serialize()

    currency_contract = 'currency'
    balances_hash = 'balances'

    balances_key = '{}{}{}{}{}'.format(currency_contract,
                                       config.INDEX_SEPARATOR,
                                       balances_hash,
                                       config.DELIMITER,
                                       w.verifying_key)

    driver = StateDriver()
    driver.set(balances_key, 1_000_000)
    driver.commit()

    return transaction_list_to_transaction_batch([tx.struct, tx2.struct], wallet=Wallet())


async def stop_server(s, timeout):
    await asyncio.sleep(timeout)
    s.stop()


def make_ipc(p):
    try:
        os.mkdir(p)
    except:
        pass

bootnodes = ['ipc:///tmp/n2', 'ipc:///tmp/n3']

mnw1 = Wallet()

dw1 = Wallet()

constitution = {
    "masternodes": {
        "vk_list": [
            mnw1.verifying_key,
        ],
        "min_quorum": 1
    },
    "delegates": {
        "vk_list": [
            dw1.verifying_key,
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


def make_tx(processor):
    w = Wallet()
    batch = TransactionBuilder(
        sender=w.verifying_key,
        contract='test',
        function='testing',
        kwargs={},
        stamps=1_000_000,
        processor=processor,
        nonce=0
    )

    batch.sign(w.signing_key)
    b = batch.serialize()

    tx = transaction_capnp.Transaction.from_bytes_packed(b)

    currency_contract = 'currency'
    balances_hash = 'balances'

    balances_key = '{}{}{}{}{}'.format(currency_contract,
                                       config.INDEX_SEPARATOR,
                                       balances_hash,
                                       config.DELIMITER,
                                       w.verifying_key)

    driver = StateDriver()
    driver.set(balances_key, 1_000_000)

    return tx

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
        masternodes = [mnw1.verifying_key, mnw2.verifying_key]

        dw1 = Wallet()
        dw2 = Wallet()
        delegates = [dw1.verifying_key, dw2.verifying_key]

        constitution = {
            "masternodes": [
                    mnw1.verifying_key,
                    mnw2.verifying_key
                ],
            "masternode_min_quorum": 1,
            "delegates": [
                    dw1.verifying_key,
                    dw2.verifying_key
                ],
            "delegate_min_quorum": 1,
            "witnesses": {},
            "schedulers": {},
            "notifiers": {},
            "enable_stamps": False,
            "enable_nonces": False
        }

        n1 = '/tmp/n1'
        make_ipc(n1)
        mn1 = Masternode(wallet=mnw1, ctx=self.ctx, socket_base=f'ipc://{n1}', bootnodes=bootnodes,
                         constitution=constitution, webserver_port=8080)

        n2 = '/tmp/n2'
        make_ipc(n2)
        mn2 = Masternode(wallet=mnw2, ctx=self.ctx, socket_base=f'ipc://{n2}', bootnodes=bootnodes,
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
                    mnw1.verifying_key,
                    mnw2.verifying_key
                ],
                "min_quorum": 1
            },
            "delegates": {
                "vk_list": [
                    dw1.verifying_key,
                    dw2.verifying_key,
                    dw3.verifying_key,
                    dw4.verifying_key
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
        mn1 = Masternode(wallet=mnw1, ctx=self.ctx, socket_base=f'ipc://{n1}', bootnodes=bootnodes,
                         constitution=constitution, webserver_port=8080, overwrite=True)

        masternodes = [mnw1.verifying_key, mnw2.verifying_key]
        delegates = [dw1.verifying_key, dw2.verifying_key, dw3.verifying_key, dw4.verifying_key]

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
            sender=w.verifying_key,
            contract='test',
            function='testing',
            kwargs={},
            stamps=1_000_000,
            processor=mnw1.verifying_key,
            nonce=0
        )

        batch.sign(w.signing_key)
        b = batch.serialize()

        tx = transaction_capnp.Transaction.from_bytes_packed(b)

        currency_contract = 'currency'
        balances_hash = 'balances'

        balances_key = '{}{}{}{}{}'.format(currency_contract,
                                           config.INDEX_SEPARATOR,
                                           balances_hash,
                                           config.DELIMITER,
                                           w.verifying_key)

        driver = StateDriver()
        driver.set(balances_key, 1_000_000)
        driver.commit()

        mn1.tx_batcher.queue.append(tx)

        mn1.network.peer_service.table.peers = {
            dw1.verifying_key: f'ipc://{d1}',
            dw2.verifying_key: f'ipc://{d2}',
            dw3.verifying_key: f'ipc://{d3}',
            dw4.verifying_key: f'ipc://{d4}'
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

        self.assertTrue(wi1.work[mnw1.verifying_key])
        self.assertTrue(wi2.work[mnw1.verifying_key])
        self.assertTrue(wi3.work[mnw1.verifying_key])
        self.assertTrue(wi4.work[mnw1.verifying_key])

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
                    mnw1.verifying_key,
                    mnw2.verifying_key
                ],
                "min_quorum": 1
            },
            "delegates": {
                "vk_list": [
                    dw1.verifying_key,
                    dw2.verifying_key,
                    dw3.verifying_key,
                    dw4.verifying_key
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
        mn1 = Masternode(
            wallet=mnw1,
            ctx=self.ctx,
            socket_base=f'ipc://{n1}',
            bootnodes=bootnodes,
            constitution=constitution,
            webserver_port=8080,
            overwrite=True
        )

        masternodes = [mnw1.verifying_key, mnw2.verifying_key]
        delegates = [dw1.verifying_key, dw2.verifying_key, dw3.verifying_key,
                     dw4.verifying_key]

        contacts = MockContacts(
            masters=masternodes,
            delegates=delegates
        )

        d1 = '/tmp/d1'
        make_ipc(d1)
        wi1 = NBNInbox(socket_id=_socket(f'ipc://{d1}/block_notifications'), ctx=self.ctx, contacts=contacts, verify=False)

        d2 = '/tmp/d2'
        make_ipc(d2)
        wi2 = NBNInbox(socket_id=_socket(f'ipc://{d2}/block_notifications'), ctx=self.ctx, contacts=contacts, verify=False)

        d3 = '/tmp/d3'
        make_ipc(d3)
        wi3 = NBNInbox(socket_id=_socket(f'ipc://{d3}/block_notifications'), ctx=self.ctx, contacts=contacts, verify=False)

        d4 = '/tmp/d4'
        make_ipc(d4)
        wi4 = NBNInbox(socket_id=_socket(f'ipc://{d4}/block_notifications'), ctx=self.ctx, contacts=contacts, verify=False)

        n2 = '/tmp/n2'
        make_ipc(n2)
        mn2 = NBNInbox(socket_id=_socket(f'ipc://{n2}/block_notifications'), ctx=self.ctx, contacts=contacts, verify=False)

        mn1.network.peer_service.table.peers = {
            dw1.verifying_key: f'ipc://{d1}',
            dw2.verifying_key: f'ipc://{d2}',
            dw3.verifying_key: f'ipc://{d3}',
            dw4.verifying_key: f'ipc://{d4}',
            mnw2.verifying_key: f'ipc://{n2}'
        }

        mn1.current_nbn = b'hello'

        async def late_send():
            await asyncio.sleep(0.3)
            await mn1.parameters.refresh()
            await mn1.send_nbn_to_everyone()

        async def stop():
            await asyncio.sleep(0.5)
            wi1.stop()
            wi2.stop()
            wi3.stop()
            wi4.stop()
            mn2.stop()
            mn1.network.stop()

        tasks = asyncio.gather(
            mn1.network.start(False),
            wi1.serve(),
            wi2.serve(),
            wi3.serve(),
            wi4.serve(),
            mn2.serve(),
            late_send(),
            stop()
        )

        self.loop.run_until_complete(tasks)

        self.assertEqual(wi1.q[0], b'hello')
        self.assertEqual(wi2.q[0], b'hello')
        self.assertEqual(wi3.q[0], b'hello')
        self.assertEqual(wi4.q[0], b'hello')
        self.assertEqual(mn2.q[0], b'hello')

    def test_send_nbn_to_everyone_except_one_doesnt_block(self):
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
                    mnw1.verifying_key,
                    mnw2.verifying_key
                ],
                "min_quorum": 1
            },
            "delegates": {
                "vk_list": [
                    dw1.verifying_key,
                    dw2.verifying_key,
                    dw3.verifying_key,
                    dw4.verifying_key
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
        mn1 = Masternode(
            wallet=mnw1,
            ctx=self.ctx,
            socket_base=f'ipc://{n1}',
            bootnodes=bootnodes,
            constitution=constitution,
            webserver_port=8080,
            overwrite=True
        )

        masternodes = [mnw1.verifying_key, mnw2.verifying_key]
        delegates = [dw1.verifying_key, dw2.verifying_key, dw3.verifying_key,
                     dw4.verifying_key]

        contacts = MockContacts(
            masters=masternodes,
            delegates=delegates
        )

        d1 = '/tmp/d1'
        make_ipc(d1)
        wi1 = NBNInbox(socket_id=_socket(f'ipc://{d1}/block_notifications'), ctx=self.ctx, contacts=contacts, verify=False)

        d2 = '/tmp/d2'
        make_ipc(d2)
        #wi2 = NBNInbox(socket_id=_socket(f'ipc://{d2}/block_notifications'), ctx=self.ctx, contacts=contacts, verify=False)

        d3 = '/tmp/d3'
        make_ipc(d3)
        wi3 = NBNInbox(socket_id=_socket(f'ipc://{d3}/block_notifications'), ctx=self.ctx, contacts=contacts, verify=False)

        d4 = '/tmp/d4'
        make_ipc(d4)
        wi4 = NBNInbox(socket_id=_socket(f'ipc://{d4}/block_notifications'), ctx=self.ctx, contacts=contacts, verify=False)

        n2 = '/tmp/n2'
        make_ipc(n2)
        mn2 = NBNInbox(socket_id=_socket(f'ipc://{n2}/block_notifications'), ctx=self.ctx, contacts=contacts, verify=False)

        mn1.network.peer_service.table.peers = {
            dw1.verifying_key: f'ipc://{d1}',
            dw2.verifying_key: f'ipc://{d2}',
            dw3.verifying_key: f'ipc://{d3}',
            dw4.verifying_key: f'ipc://{d4}',
            mnw2.verifying_key: f'ipc://{n2}'
        }

        mn1.current_nbn = b'hello'

        async def late_send():
            await asyncio.sleep(0.3)
            await mn1.parameters.refresh()
            return await mn1.send_nbn_to_everyone()

        async def stop():
            await asyncio.sleep(0.5)
            wi1.stop()
            wi3.stop()
            wi4.stop()
            mn2.stop()
            mn1.network.stop()

        tasks = asyncio.gather(
            mn1.network.start(False),
            wi1.serve(),
            wi3.serve(),
            wi4.serve(),
            mn2.serve(),
            late_send(),
            stop()
        )

        self.loop.run_until_complete(tasks)

        _, _, _, _, _, r, _ = self.loop.run_until_complete(tasks)

        # Make sure the right socket failed
        for rr in r:
            if not rr[0]:
                self.assertEqual(rr[1], f'ipc://{d2}/block_notifications')

        self.assertEqual(wi1.q[0], b'hello')
        #self.assertEqual(wi2.q[0], b'hello')
        self.assertEqual(wi3.q[0], b'hello')
        self.assertEqual(wi4.q[0], b'hello')
        self.assertEqual(mn2.q[0], b'hello')

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
                    mnw1.verifying_key,
                    mnw2.verifying_key
                ],
                "min_quorum": 1
            },
            "delegates": {
                "vk_list": [
                    dw1.verifying_key,
                    dw2.verifying_key,
                    dw3.verifying_key,
                    dw4.verifying_key
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
        mn1 = Masternode(wallet=mnw1, ctx=self.ctx, socket_base=f'ipc://{n1}', bootnodes=bootnodes,
                         constitution=constitution, webserver_port=8080, overwrite=True)

        masternodes = [mnw1.verifying_key, mnw2.verifying_key]
        delegates = [dw1.verifying_key, dw2.verifying_key, dw3.verifying_key,
                     dw4.verifying_key]

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
            sender=w.verifying_key,
            contract='test',
            function='testing',
            kwargs={},
            stamps=1_000_000,
            processor=mnw1.verifying_key,
            nonce=0
        )

        batch.sign(w.signing_key)
        b = batch.serialize()

        tx = transaction_capnp.Transaction.from_bytes_packed(b)

        currency_contract = 'currency'
        balances_hash = 'balances'

        balances_key = '{}{}{}{}{}'.format(currency_contract,
                                           config.INDEX_SEPARATOR,
                                           balances_hash,
                                           config.DELIMITER,
                                           w.verifying_key)

        driver = StateDriver()
        driver.set(balances_key, 1_000_000)
        driver.commit()

        mn1.tx_batcher.queue.append(tx)

        mn1.network.peer_service.table.peers = {
            dw1.verifying_key: f'ipc://{d1}',
            dw2.verifying_key: f'ipc://{d2}',
            dw3.verifying_key: f'ipc://{d3}',
            dw4.verifying_key: f'ipc://{d4}'
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

        self.assertTrue(wi1.work[mnw1.verifying_key])
        self.assertTrue(wi2.work[mnw1.verifying_key])
        self.assertTrue(wi4.work[mnw1.verifying_key])

    def test_process_blocks_single_contact_updates_correctly(self):
        # Setup masternode
        # Setup a socket to send finished work to
        # Execute real transaction on delegate that just isnt started?

        # Somehow calculate what the block should be after processing
        # Check that the driver updates the state with the block T1
        # Check that the blocks updates the blocks with the block (ha) T2

        # Test to see that a NBN gets sent out because the block is finished T3
        #
        pass

    # def test_process_blocks_works(self):
    #     bootnodes = ['ipc:///tmp/n1', 'ipc:///tmp/n3']
    #
    #     mnw1 = Wallet()
    #
    #     dw1 = Wallet()
    #
    #     constitution = {
    #         "masternodes": {
    #             "vk_list": [
    #                 mnw1.verifying_key,
    #             ],
    #             "min_quorum": 1
    #         },
    #         "delegates": {
    #             "vk_list": [
    #                 dw1.verifying_key,
    #             ],
    #             "min_quorum": 1
    #         },
    #         "witnesses": {},
    #         "schedulers": {},
    #         "notifiers": {},
    #         "enable_stamps": False,
    #         "enable_nonces": False
    #     }
    #
    #
    #     # Delegate like thing
    #     n3 = '/tmp/n3'
    #     make_ipc(n3)
    #     d1 = Network(wallet=dw1, ctx=self.ctx, socket_base=f'ipc://{n3}',
    #                  bootnodes=bootnodes, mn_to_find=[mnw1.verifying_key], del_to_find=[dw1.verifying_key])
    #
    #
    #
    #     n1 = '/tmp/n1'
    #     make_ipc(n1)
    #
    #     m = Masternode(
    #         wallet=mnw1,
    #         ctx=self.ctx,
    #         socket_base=f'ipc://{n1}',
    #         bootnodes=bootnodes,
    #         constitution=constitution,
    #         webserver_port=8080,
    #         overwrite=True
    #     )
    #
    #     async def add_tx():
    #         await asyncio.sleep(0.4)
    #         m.tx_batcher.queue.append(make_tx(mnw1.verifying_key))
    #
    #     async def boot():
    #         await m.start()
    #         await m.process_blocks()
    #
    #     tasks = asyncio.gather(
    #         boot(),
    #         d1.start(),
    #         add_tx()
    #     )
    #
    #     self.loop.run_until_complete(tasks)


    def test_retreived_subblocks_serialize_to_block_properly_single_block(self):
        bootnodes = ['ipc:///tmp/n2', 'ipc:///tmp/n3']

        mnw1 = Wallet()

        dw1 = Wallet()

        constitution = {
            "masternodes": {
                "vk_list": [
                    mnw1.verifying_key,
                ],
                "min_quorum": 1
            },
            "delegates": {
                "vk_list": [
                    dw1.verifying_key,
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

        m = Masternode(
            wallet=mnw1,
            ctx=self.ctx,
            socket_base=f'ipc://{n1}',
            bootnodes=bootnodes,
            constitution=constitution,
            webserver_port=8080,
            overwrite=True
        )

        input_hash = secrets.token_bytes(32)
        sbc = random_txs.sbc_from_txs(input_hash, b'\x00' * 32, w=dw1, idx=0, poisoned_sig=b'\x00' * 64)
        b = m.sbcs_to_block([sbc])

        print(b)

    def test_new_blockchain_boot_completes_if_nbn_inbox_recieved(self):
        m = Masternode(
            wallet=mnw1,
            ctx=self.ctx,
            socket_base='ipc:///tmp/n1',
            bootnodes=bootnodes,
            constitution=constitution,
            webserver_port=8080,
            overwrite=True
        )

        # For mocking
        m.nbn_inbox.verify = False

        async def send_nbn():
            await asyncio.sleep(0.3)
            socket = self.ctx.socket(zmq.DEALER)
            socket.connect('ipc:///tmp/n1/block_notifications')
            await socket.send(b'123')
            await asyncio.sleep(0.3)
            m.nbn_inbox.stop()

        tasks = asyncio.gather(
            m.nbn_inbox.serve(),
            m.new_blockchain_boot(),
            send_nbn()
        )

        self.loop.run_until_complete(tasks)

    def test_new_blockchain_boot_completes_if_tx_batch_filled(self):
        m = Masternode(
            wallet=mnw1,
            ctx=self.ctx,
            socket_base='ipc:///tmp/n1',
            bootnodes=bootnodes,
            constitution=constitution,
            webserver_port=8080,
            overwrite=True
        )

        # For mocking
        async def add_tx_batch():
            m.tx_batcher.queue.append(b'123')

        tasks = asyncio.gather(
            m.new_blockchain_boot(),
            add_tx_batch()
        )

        self.loop.run_until_complete(tasks)

    def test_new_blockchain_boot_sends_genesis_block_if_tx_batch(self):
        m = Masternode(
            wallet=mnw1,
            ctx=self.ctx,
            socket_base='ipc:///tmp/n1',
            bootnodes=bootnodes,
            constitution=constitution,
            webserver_port=8080,
            overwrite=True
        )

        m.parameters.sockets = {
            dw1.verifying_key: 'ipc:///tmp/n2'
        }

        # For mocking
        async def add_tx_batch():
            m.tx_batcher.queue.append(b'123')

        async def recv_tx_batch():
            socket = self.ctx.socket(zmq.ROUTER)
            socket.bind('ipc:///tmp/n2/block_notifications')
            _id, msg = await socket.recv_multipart()
            return msg

        tasks = asyncio.gather(
            m.new_blockchain_boot(),
            add_tx_batch(),
            recv_tx_batch()
        )

        _, _, msg = self.loop.run_until_complete(tasks)

        self.assertEqual(msg, canonical.dict_to_msg_block(lamden.nodes.masternode.masternode.get_genesis_block()))

    def test_join_quorum_updates_with_block_if_nbn_has_block(self):
        m = Masternode(
            wallet=mnw1,
            ctx=self.ctx,
            socket_base='ipc:///tmp/n1',
            bootnodes=bootnodes,
            constitution=constitution,
            webserver_port=8080,
            overwrite=True
        )

        block = random_txs.random_block()

        m.nbn_inbox.q.append(block.to_dict())

        k = block.subBlocks[0].transactions[0].state[0].server_key
        v = block.subBlocks[0].transactions[0].state[0].value

        self.assertIsNone(m.client.raw_driver.get_direct(k))

        async def add_tx_queue():
            await asyncio.sleep(0.3)
            m.tx_batcher.queue.append(b'blah')
            m.nbn_inbox.q.append(block.to_dict())

        tasks = asyncio.gather(
            m.join_quorum(),
            add_tx_queue()
        )

        self.loop.run_until_complete(tasks)

        self.assertEqual(m.client.raw_driver.get_direct(k), v)

    def test_send_work_returns_none_if_no_one_online(self):
        m = Masternode(
            wallet=mnw1,
            ctx=self.ctx,
            socket_base='ipc:///tmp/n1',
            bootnodes=bootnodes,
            constitution=constitution,
            webserver_port=8080,
            overwrite=True
        )

        r = self.loop.run_until_complete(m.send_work())

        self.assertIsNone(r)

