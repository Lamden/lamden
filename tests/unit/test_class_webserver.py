from contracting.client import ContractingClient
from contracting.db.driver import ContractDriver, decode, encode, FSDriver
from lamden import storage
from lamden.crypto.transaction import build_transaction
from lamden.crypto.wallet import Wallet
from lamden.nodes.events import EventWriter, Event, EventService
from lamden.nodes.filequeue import FileQueue
from lamden.nodes.hlc import HLC_Clock
from lamden.nodes.masternode.webserver import WebServer
from lamden.storage import BlockStorage
from multiprocessing import Process
from tests.unit.helpers.mock_blocks import generate_blocks
from unittest import TestCase
import asyncio
import copy
import json
import pathlib
import shutil
import time
import websockets

EVENT_SERVICE_PORT = 8000
SAMPLE_TOPIC = 'new_block'

class TestClassWebserver(TestCase):
    def setUp(self):
        self.storage_root = pathlib.Path().cwd().joinpath('test_class_webserver')
        if self.storage_root.is_dir():
            shutil.rmtree(self.storage_root)
        self.storage_root.mkdir()

        self.w = Wallet()
        self.blocks = BlockStorage(root=self.storage_root)
        self.driver = ContractDriver(driver=FSDriver(root=self.storage_root.joinpath('state')))
        self.ws = WebServer(
            wallet=self.w,
            contracting_client=ContractingClient(driver=self.driver),
            blocks=self.blocks,
            driver=self.driver,
            queue=FileQueue(root=self.storage_root),
            nonces=storage.NonceStorage(nonce_collection=self.storage_root.joinpath('nonces'), pending_collection=self.storage_root.joinpath('pending_nonces'))
        )

    def tearDown(self):
        shutil.rmtree(self.storage_root)

    def test_ping(self):
        _, response = self.ws.app.test_client.get('/ping')
        self.assertDictEqual(response.json, {'status': 'online'})

    def test_get_id(self):
        _, response = self.ws.app.test_client.get('/id')
        self.assertDictEqual(response.json, {'verifying_key': self.w.verifying_key})

    def test_get_nonce_pending_nonce_is_none_returns_0(self):
        w2 = Wallet()
        _, response = self.ws.app.test_client.get('/nonce/{}'.format(w2.verifying_key))

        expected = {'nonce': 0, 'processor': self.w.verifying_key, 'sender': w2.verifying_key}

        self.assertDictEqual(response.json, expected)

    def test_get_nonce_pending_nonce_is_not_none_returns_pending_nonce(self):
        w2 = Wallet()

        self.ws.nonces.set_pending_nonce(
            sender=w2.verifying_key,
            processor=self.w.verifying_key,
            value=123
        )

        _, response = self.ws.app.test_client.get('/nonce/{}'.format(w2.verifying_key))

        expected = {'nonce': 124, 'processor': self.w.verifying_key, 'sender': w2.verifying_key}

        self.assertDictEqual(expected, response.json)

    def test_get_nonce_pending_nonce_is_none_but_nonce_is_not_returns_nonce(self):
        w2 = Wallet()

        self.ws.nonces.set_nonce(processor=self.w.verifying_key, sender=w2.verifying_key, value=555)

        _, response = self.ws.app.test_client.get('/nonce/{}'.format(w2.verifying_key))

        expected = {'nonce': 556, 'processor': self.w.verifying_key, 'sender': w2.verifying_key}

        self.assertDictEqual(response.json, expected)

    def test_get_contracts_returns_list_of_contracts(self):
        _, response = self.ws.app.test_client.get('/contracts')

        self.assertDictEqual(response.json, {'contracts': ['submission']})

    def test_get_contract_returns_contract_code(self):
        _, response = self.ws.app.test_client.get('/contracts/submission')

        f = open(self.ws.client.submission_filename)
        code = f.read()
        f.close()

        expected = {'name': 'submission', 'code': code}

        self.assertDictEqual(response.json, expected)

    def test_get_contract_that_does_not_exist_returns_error(self):
        _, response = self.ws.app.test_client.get('/contracts/blah')

        self.assertDictEqual(response.json, {'error': 'blah does not exist'})

    def test_get_contract_methods_returns_all_methods(self):
        _, response = self.ws.app.test_client.get('/contracts/submission/methods')

        self.assertDictEqual(response.json,
            {
                'methods': [
                    {
                        'name': 'submit_contract',
                        'arguments': [
                            {
                                'name': 'name',
                                'type': 'str'
                            },
                            {
                                'name': 'code',
                                'type': 'str'
                            },
                            {
                                'name': 'owner',
                                'type': 'Any'
                            },
                            {
                                'name':'constructor_args',
                                'type': 'dict'
                            }
                        ]
                    },
                    {
                        'name': 'change_developer',
                        'arguments': [
                            {
                                'name': 'contract',
                                'type': 'str'
                            },
                            {
                                'name': 'new_developer',
                                'type': 'str'
                            }
                        ]
                    }
                ]
            })

    def test_get_contract_method_returns_error_if_does_not_exist(self):
        _, response = self.ws.app.test_client.get('/contracts/blah/methods')

        self.assertDictEqual(response.json, {'error': 'blah does not exist'})

    def test_get_variable_returns_value_if_it_exists(self):
        code = '''
v = Variable()

@construct
def seed():
    v.set(12345)

@export
def get():
    return v.get()
        '''

        self.ws.client.submit(f=code, name='testing')
        self.ws.client.raw_driver.commit()

        _, response = self.ws.app.test_client.get('/contracts/testing/v')

        self.assertDictEqual(response.json, {'value': 12345})

    def test_get_variables_returns_variable_list(self):
            code = '''
v = Variable()
howdy = Variable()
h = Hash()
hash2 = Hash()

@construct
def seed():
    a = 123
    v.set(12345)

@export
def get():
    return v.get()
        '''

            self.ws.client.submit(f=code, name='testing')
            self.ws.client.raw_driver.commit()

            _, response = self.ws.app.test_client.get('/contracts/testing/variables')

            expected = {
                'variables': ['v', 'howdy'],
                'hashes': ['h', 'hash2']
            }

            self.assertDictEqual(response.json, expected)

    def test_get_variables_returns_error_if_contract_does_not_exist(self):
        _, response = self.ws.app.test_client.get('/contracts/blah/variables')

        self.assertDictEqual(response.json, {'error': 'blah does not exist'})

    def test_get_variable_returns_error_if_contract_does_not_exist(self):
        _, response = self.ws.app.test_client.get('/contracts/blah/v')

        self.assertDictEqual(response.json, {'error': 'blah does not exist'})

    def test_get_variable_returns_none_if_variable_does_not_exist(self):
        code = '''
v = Variable()

@construct
def seed():
    v.set(12345)

@export
def get():
    return v.get()
        '''

        self.ws.client.submit(f=code, name='testing')
        self.ws.client.raw_driver.commit()

        _, response = self.ws.app.test_client.get('/contracts/testing/x')

        self.assertDictEqual(response.json, {'value': None})

    def test_get_variable_works_for_single_key(self):
        code = '''
h = Hash()

@construct
def seed():
    h['stu'] = 99999

@export
def get():
    return h['stu']
        '''

        self.ws.client.submit(f=code, name='testing')
        self.ws.client.raw_driver.commit()

        _, response = self.ws.app.test_client.get('/contracts/testing/h?key=stu')

        self.assertDictEqual(response.json, {'value': 99999})

    def test_get_variable_works_for_multihashes(self):
        code = '''
h = Hash()

@construct
def seed():
    h['stu'] = 99999
    h['stu', 'hello', 'jabroni'] = 77777

@export
def get():
    return h['stu']
        '''

        self.ws.client.submit(f=code, name='testing')
        self.ws.client.raw_driver.commit()

        _, response = self.ws.app.test_client.get('/contracts/testing/h?key=stu,hello,jabroni')

        self.assertDictEqual(response.json, {'value': 77777})

    def test_get_variable_multihash_returns_none(self):
        code = '''
h = Hash()

@construct
def seed():
    h['stu'] = 99999
    h['stu', 'hello', 'jabroni'] = 77777

@export
def get():
    return h['stu']
        '''

        self.ws.client.submit(f=code, name='testing')
        self.ws.client.raw_driver.commit()

        _, response = self.ws.app.test_client.get('/contracts/testing/h?key=notstu,hello,jabroni')

        self.assertDictEqual(response.json, {'value': None})

        _, response = self.ws.app.test_client.get('/contracts/testing/h?key=notstu')

        self.assertDictEqual(response.json, {'value': None})

    def test_get_latest_block(self):
        blocks = generate_blocks(
            number_of_blocks=2,
            starting_block_num=0,
            prev_block_hash='0'*64,
            prev_block_hlc=HLC_Clock().get_new_hlc_timestamp()
        )
        for b in blocks:
            self.ws.blocks.store_block(copy.deepcopy(b))
        storage.set_latest_block_height(2, driver=self.ws.driver)
        self.ws.driver.commit()

        _, response = self.ws.app.test_client.get('/latest_block')
        self.assertDictEqual(response.json, blocks[1])

    def test_get_latest_block_num(self):
        storage.set_latest_block_height(1234, self.ws.driver)
        self.ws.driver.commit()

        _, response = self.ws.app.test_client.get('/latest_block_num')
        self.assertDictEqual(response.json, {'latest_block_number': 1234})

    def test_get_latest_block_hash(self):
        h = '0' * 64
        storage.set_latest_block_hash(h, self.ws.driver)

        _, response = self.ws.app.test_client.get('/latest_block_hash')

        self.assertDictEqual(response.json, {'latest_block_hash': h})

    def test_get_block_by_num_that_exists(self):
        block = generate_blocks(
            number_of_blocks=1,
            starting_block_num=0,
            prev_block_hash='0'*64,
            prev_block_hlc=HLC_Clock().get_new_hlc_timestamp()
        )[0]

        self.ws.blocks.store_block(copy.deepcopy(block))

        _, response = self.ws.app.test_client.get('/blocks?num=1')

        self.assertDictEqual(response.json, block)

    def test_get_block_by_num_that_doesnt_exist_returns_error(self):
        _, response = self.ws.app.test_client.get('/blocks?num=1000')

        self.assertDictEqual(response.json, {'error': 'Block not found.'})

    def test_get_block_by_hash_that_exists(self):
        block = generate_blocks(
            number_of_blocks=1,
            starting_block_num=0,
            prev_block_hash='0'*64,
            prev_block_hlc=HLC_Clock().get_new_hlc_timestamp()
        )[0]

        self.ws.blocks.store_block(copy.deepcopy(block))

        _, response = self.ws.app.test_client.get(f'/blocks?hash={block["hash"]}')
        self.assertDictEqual(response.json, block)

    def test_get_block_by_hash_that_doesnt_exist_returns_error(self):
        _, response = self.ws.app.test_client.get('/blocks?hash=zzz')
        self.assertDictEqual(response.json, {'error': 'Block not found.'})

    def test_get_block_no_args_returns_error(self):
        _, response = self.ws.app.test_client.get('/blocks')
        self.assertDictEqual(response.json, {'error': 'No number or hash provided.'})

    def test_bad_transaction_returns_a_TransactionException(self):
        tx = build_transaction(
            wallet=Wallet(),
            processor='b' * 64,
            stamps=123,
            nonce=0,
            contract='currency',
            function='transfer',
            kwargs={
                'amount': 123,
                'to': 'jeff'
            }
        )
        _, response = self.ws.app.test_client.post('/', data=tx)
        self.assertDictEqual(response.json, {'error': 'Transaction processor does not match expected processor.'})

    def test_good_transaction_is_put_into_queue(self):
        self.assertEqual(len(self.ws.queue), 0)

        w = Wallet()

        self.ws.client.set_var(
            contract='currency',
            variable='balances',
            arguments=[w.verifying_key],
            value=1_000_000
        )

        self.ws.client.set_var(
            contract='stamp_cost',
            variable='S',
            arguments=['value'],
            value=1_000_000
        )
        self.ws.client.raw_driver.commit()

        tx = build_transaction(
            wallet=w,
            processor=self.ws.wallet.verifying_key,
            stamps=6000,
            nonce=0,
            contract='currency',
            function='transfer',
            kwargs={
                'amount': 123,
                'to': 'jeff'
            }
        )

        _, response = self.ws.app.test_client.post('/', data=tx)

        self.assertEqual(len(self.ws.queue), 1)

    def test_fixed_objects_do_not_fail_signature(self):
        self.assertEqual(len(self.ws.queue), 0)

        w = Wallet()

        self.ws.client.set_var(
            contract='currency',
            variable='balances',
            arguments=[w.verifying_key],
            value=1_000_000
        )

        self.ws.client.set_var(
            contract='stamp_cost',
            variable='S',
            arguments=['value'],
            value=1_000_000
        )

        tx = build_transaction(
            wallet=w,
            processor=self.ws.wallet.verifying_key,
            stamps=6000,
            nonce=0,
            contract='currency',
            function='transfer',
            kwargs={
                'amount': {'__fixed__': '1.0'},
                'to': 'jeff'
            }
        )

        _, response = self.ws.app.test_client.post('/', data=tx)

        self.assertEqual(1, len(self.ws.queue))

    def test_submit_transaction_error_if_queue_full(self):
        for i in range(10_000):
            self.ws.queue.append(bytes(i))

        tx = build_transaction(
            wallet=Wallet(),
            processor=self.ws.wallet.verifying_key,
            stamps=123,
            nonce=0,
            contract='currency',
            function='transfer',
            kwargs={
                'amount': 123,
                'to': 'jeff'
            }
        )

        _, response = self.ws.app.test_client.post('/', data=tx)

        self.assertDictEqual(response.json, {'error': 'Queue full. Resubmit shortly.'})

    def test_get_tx_by_hash_if_it_exists(self):
        block = generate_blocks(
            number_of_blocks=1,
            starting_block_num=0,
            prev_block_hash='0'*64,
            prev_block_hlc=HLC_Clock().get_new_hlc_timestamp()
        )[0]
        block['processed']['hash'] = 'beef'

        self.ws.blocks.store_block(copy.deepcopy(block))

        _, response = self.ws.app.test_client.get(f'/tx?hash={block["processed"]["hash"]}')
        self.assertDictEqual(response.json, block['processed'])

    def test_malformed_tx_returns_error(self):
        tx = b'"df:'

        _, response = self.ws.app.test_client.post('/', data=tx)

        self.assertDictEqual(response.json, {'error': 'Malformed request body.'})

    def test_tx_with_error_returns_exception(self):
        tx = build_transaction(
            wallet=Wallet(),
            processor=self.ws.wallet.verifying_key,
            stamps=123,
            nonce=0,
            contract='currency',
            function='transfer',
            kwargs={
                'amount': 123,
                'to': 'jeff'
            }
        )

        tx = decode(tx)
        tx['payload']['stamps_supplied'] = -123
        tx = encode(tx)

        _, response = self.ws.app.test_client.post('/', data=tx)

        self.assertDictEqual(response.json, {'error': 'Transaction is not formatted properly.'})

    def test_get_constitution_returns_correct_state(self):
        self.ws.client.set_var(
            contract='masternodes',
            variable='S',
            arguments=['members'],
            value=['1', '2', '3']
        )

        self.ws.client.set_var(
            contract='delegates',
            variable='S',
            arguments=['members'],
            value=['4', '5', '6']
        )

        self.ws.client.raw_driver.commit()

        _, response = self.ws.app.test_client.get('/constitution')

        self.assertDictEqual(response.json, {
            'masternodes': ['1', '2', '3'],
            'delegates': ['4', '5', '6'],
        })

    def test_error_returned_if_tx_hash_not_provided(self):
        _, response = self.ws.app.test_client.get('/tx')

        self.assertDictEqual(response.json, {'error': 'No tx hash provided.'})

    def test_error_returned_if_tx_hash_malformed(self):
        _, response = self.ws.app.test_client.get('/tx?hash=hello')

        self.assertDictEqual(response.json, {'error': 'Malformed hash.'})

    def test_error_returned_if_no_tx_hash(self):
        _, response = self.ws.app.test_client.get('/tx?hash=' + 'a' * 64)

        self.assertDictEqual(response.json, {'error': 'Transaction not found.'})

    def test_js_encoded_tx_works(self):
        pass

class TestWebserverWebsockets(TestCase):
    service_process = None

    @classmethod
    def setUpClass(cls):
        TestWebserverWebsockets.service_process = Process(target=lambda: EventService(EVENT_SERVICE_PORT).run())
        TestWebserverWebsockets.service_process.start()
        time.sleep(0.1)

    @classmethod
    def tearDownClass(cls):
        TestWebserverWebsockets.service_process.terminate()

    def setUp(self):
        self.ws = WebServer(
            wallet=Wallet(),
            contracting_client=ContractingClient(),
            blocks=BlockStorage(),
            driver=ContractDriver(),
            topics=[SAMPLE_TOPIC]
        )
        asyncio.set_event_loop(asyncio.new_event_loop())
        self.loop = asyncio.get_event_loop()
        self.server = self.loop.run_until_complete(
            asyncio.ensure_future(
                self.ws.app.create_server(host='0.0.0.0', port=self.ws.port, return_asyncio_server=True)
            )
        )
        self.loop.run_until_complete(self.ws.sio.connect(f'http://localhost:{EVENT_SERVICE_PORT}'))

        self.websocket = None
        self.messages = []

    def tearDown(self):
        self.await_async_task(self.websocket.close)
        self.loop.run_until_complete(self.ws.sio.disconnect())
        self.server.close()
        self.loop.run_until_complete(self.server.wait_closed())
        self.loop.close()

    def await_async_task(self, task):
        tasks = asyncio.gather(
            task()
        )
        loop = asyncio.get_event_loop()
        loop.run_until_complete(tasks)

    async def ws_connect(self):
        self.websocket = await websockets.connect(f'ws://localhost:{self.ws.port}')

    async def ws_get_next_message(self):
        self.messages.append(json.loads(await self.websocket.recv()))

    def test_ws_can_connect_to_webserver_get_latest_block_event(self):
        self.await_async_task(self.ws_connect)
        self.await_async_task(self.ws_get_next_message)

        self.assertEqual(len(self.ws.ws_clients), 1)
        self.assertEqual(self.messages[0]['event'], 'latest_block')

    def test_ws_client_receive_events_from_webserver(self):
        self.await_async_task(self.ws_connect)
        self.await_async_task(self.ws_get_next_message)
        EventWriter().write_event(Event(topics=self.ws.topics, data={'number': 101, 'hash': 'xoxo'}))
        self.await_async_task(self.ws_get_next_message)
        self.assertDictEqual(self.messages[1], {'event': SAMPLE_TOPIC, 'data': {'number': 101, 'hash': 'xoxo'}})
