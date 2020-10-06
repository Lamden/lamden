from lamden.nodes.delegate import execution, work
from lamden import router, network
from lamden.nodes import base
from lamden.logger.base import get_logger
import asyncio
import time
from lamden.crypto.wallet import verify
from contracting.execution.executor import Executor
from lamden.crypto import transaction
from contracting.client import ContractingClient
from lamden import storage
from collections import defaultdict
WORK_SERVICE = 'work'


class WorkProcessor(router.Processor):
    def __init__(self, client: ContractingClient, nonces: storage.NonceStorage, debug=True, expired_batch=5,
                 tx_timeout=5):
        self.new_work = defaultdict(list)

        self.log = get_logger('Work Inbox')
        self.log.propagate = debug

        self.masters = []
        self.expired_batch = expired_batch
        self.tx_timeout = tx_timeout

        self.client = client
        self.nonces = nonces

    async def process_message(self, msg):
        self.log.info(f'Received work from {msg["sender"][:8]}')
        if msg['sender'] not in self.masters:
            self.log.error(f'TX Batch received from non-master {msg["sender"][:8]}')
            return

        shim = {
            'transactions': [],
            'timestamp': int(time.time()),
            'signature': '0' * 128,
            'input_hash': msg["sender"],
            'sender': msg["sender"]
        }

        if not verify(vk=msg['sender'], msg=msg['input_hash'], signature=msg['signature']):
            self.log.error(f'Invalidly signed TX Batch received from master {msg["sender"][:8]}')
            return self.new_work[msg['sender']].append(shim)

        if int(time.time()) - msg['timestamp'] > self.expired_batch:
            self.log.error(f'Expired TX Batch received from master {msg["sender"][:8]}')
            return self.new_work[msg['sender']].append(shim)

        # Add padded!
        # Iterate and delete transactions from list that fail
        good_transactions = []
        for tx in msg['transactions']:
            try:
                transaction.transaction_is_valid(
                    transaction=tx,
                    expected_processor=msg['sender'],
                    client=self.client,
                    nonces=self.nonces,
                    strict=False,
                    timeout=self.expired_batch + self.tx_timeout
                )
                good_transactions.append(tx)
            except transaction.TransactionException as e:
                self.log.error(f'TX in batch has error: {type(e)}')

        # Replace transactions with ones that do not pass.
        msg['transactions'] = good_transactions

        self.new_work[msg['sender']].append(msg)
        self.log.info(f'{msg["sender"][:8]} has {len(self.new_work[msg["sender"]])} batches of work to do.')

    async def gather_transaction_batches(self, masters: list, timeout=10):
        # Wait until the queue is filled before starting timeout
        self.masters = masters

        ready = False
        while not ready:
            for master in masters:
                if len(self.new_work[master]) > 0:
                    ready = True
            await asyncio.sleep(0)

        # Now wait until the rest come in or the timeout is triggered
        next_work = []
        start = time.time()
        while len(next_work) < len(masters) and time.time() - start < timeout:
            for master in masters:
                if len(self.new_work[master]) > 0:
                    next_work.append(self.new_work[master].pop(0))
            await asyncio.sleep(0)

        return next_work


class Delegate(base.Node):
    def __init__(self, parallelism=4, *args, **kwargs):

        super().__init__(*args, **kwargs)

        # Number of core / processes we push to
        self.parallelism = parallelism
        self.executor = Executor(driver=self.driver)
        self.transaction_executor = execution.SerialExecutor(executor=self.executor)

        self.work_processor = WorkProcessor(client=self.client, nonces=self.nonces)
        self.router.add_service(WORK_SERVICE, self.work_processor)

        self.upgrade_manager.node_type = 'delegate'

        self.log = get_logger(f'Delegate {self.wallet.vk_pretty[4:12]}')

    async def start(self):
        self.log.debug('Starting')
        await super().start()

        members = self.driver.get_var(contract='delegates', variable='S', arguments=['members'])
        assert self.wallet.verifying_key in members, 'You are not a delegate!'

        asyncio.ensure_future(self.run())

    async def acquire_work(self):
        current_masternodes = self.client.get_var(contract='masternodes', variable='S', arguments=['members'])

        w = await self.work_processor.gather_transaction_batches(masters=current_masternodes)

        self.log.info(f'Got {len(w)} batch(es) of work')

        expected_masters = set(current_masternodes)
        work.pad_work(work=w, expected_masters=list(expected_masters))

        return work.filter_work(w)

    async def update_sockets(self):
        mns = self.get_masternode_peers()
        iterator = iter(mns.items())
        vk, ip = next(iterator)

        peers = await router.secure_request(
            msg={},
            service=network.PEER_SERVICE,
            cert_dir=self.socket_authenticator.cert_dir,
            wallet=self.wallet,
            ctx=self.ctx,
            vk=vk,
            ip=ip
        )

        if peers is not None:
            self.network.update_peers(peers=peers)

    async def wait_for_new_block_confirmation(self):
        self.log.info('Waiting for block confirmation...')
        block = await self.new_block_processor.wait_for_next_nbn()
        self.process_new_block(block)

        await self.update_sockets()

    async def process_new_work(self):
        if len(self.get_masternode_peers()) == 0:
            return

        filtered_work = await self.acquire_work()

        # Run mini catch up here to prevent 'desyncing'
        self.log.info(f'{len(self.new_block_processor.q)} new block(s) to process before execution.')

        while len(self.new_block_processor.q) > 0:
            block = self.new_block_processor.q.pop(0)
            self.process_new_block(block)

        results = self.transaction_executor.execute_work(
            driver=self.driver,
            work=filtered_work,
            wallet=self.wallet,
            previous_block_hash=self.current_hash,
            current_height=self.current_height,
            stamp_cost=self.client.get_var(contract='stamp_cost', variable='S', arguments=['value'])
        )

        await router.secure_multicast(
            msg=results,
            service=base.CONTENDER_SERVICE,
            cert_dir=self.socket_authenticator.cert_dir,
            wallet=self.wallet,
            peer_map=self.get_masternode_peers(),
            ctx=self.ctx
        )

        self.log.info(f'Work execution complete. Sending to masters.')

        self.new_block_processor.clean(self.current_height)
        self.driver.clear_pending_state()

    async def loop(self):
        self.log.info('=== ENTERING PROCESS NEW WORK STATE ===')
        self.upgrade_manager.version_check(constitution=self.make_constitution())

        await self.process_new_work()

        self.log.info('=== ENTERING BLOCK CONFIRMATION STATE ===')
        await self.wait_for_new_block_confirmation()

    async def run(self):
        self.log.info('Done starting. Beginning participation in consensus.')
        while self.running:
            await self.loop()

    def stop(self):
        self.router.stop()
