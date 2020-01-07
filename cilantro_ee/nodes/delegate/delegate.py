from cilantro_ee.nodes.new_block_inbox import NBNInbox
from cilantro_ee.nodes.work_inbox import WorkInbox
from cilantro_ee.storage.vkbook import VKBook
from cilantro_ee.storage.state import MetaDataStorage
from cilantro_ee.storage.state import NonceManager
from cilantro_ee.networking.parameters import ServiceType, NetworkParameters, Parameters

from cilantro_ee.messages.message import Message
from cilantro_ee.messages.message_type import MessageType

from cilantro_ee.containers.merkle_tree import merklize

from cilantro_ee.crypto.wallet import Wallet

from contracting.client import ContractingClient
from contracting.stdlib.bridge.decimal import ContractingDecimal
from contracting.stdlib.bridge.time import Datetime

import asyncio
import heapq
from datetime import datetime
import zmq.asyncio
import os
import capnp
import cilantro_ee.messages.capnp_impl.capnp_struct as schemas

transaction_capnp = capnp.load(os.path.dirname(schemas.__file__) + '/transaction.capnp')
subblock_capnp = capnp.load(os.path.dirname(schemas.__file__) + '/subblock.capnp')


class BlockManager:
    def __init__(self, socket_base, ctx, wallet: Wallet, contacts: VKBook, network_parameters=NetworkParameters(),
                 validity_timeout=1000, parallelism=4, client=ContractingClient(), driver=MetaDataStorage(), nonces=NonceManager()):

        # VKBook, essentially
        self.contacts = contacts
        self.parameters = Parameters(
            socket_base=socket_base,
            ctx=ctx,
            wallet=wallet,
            network_parameters=network_parameters,
            contacts=self.contacts)

        # Number of core / processes we push to
        self.parallelism = parallelism
        self.network_parameters = network_parameters
        self.ctx = ctx
        self.wallet = wallet

        # How long until a tx batch is 'stale' and no longer valid
        self.validity_timeout = validity_timeout

        self.client = client
        self.driver = driver
        self.nonces = nonces

        self.nbn_inbox = NBNInbox(
            socket_id=self.network_parameters.resolve(socket_base, ServiceType.BLOCK_NOTIFICATIONS, bind=True),
            contacts=self.contacts,
            driver=self.driver,
            ctx=self.ctx
        )
        self.work_inbox = WorkInbox(
            socket_id=self.network_parameters.resolve(socket_base, ServiceType.INCOMING_WORK, bind=True),
            nonces=self.nonces,
            validity_timeout=1000,
            contacts=self.contacts,
            ctx=self.ctx
        )
        self.pending_sbcs = {}
        self.running = False

    async def send_out(self, msg, socket_id):
        socket = self.ctx.socket(zmq.DEALER)
        socket.connect(str(socket_id))

        try:
            socket.send(msg, zmq.NOBLOCK)
            return True
        except zmq.ZMQError:
            return False

    def did_sign_block(self, block):
        if len(self.pending_sbcs) == 0:
            return False

        for sub_block in block.subBlocks:
            if self.pending_sbcs.get(sub_block.merkleRoot) is None:
                return False

        return True

    async def run(self):
        while self.running:
            # wait for NBN
            block = await self.nbn_inbox.wait_for_next_nbn()

            # If its the block that you worked on, commit the db
            # AKA if you signed the block
            if self.did_sign_block(block):
                self.client.raw_driver.commit()
            else:
                # Else, revert the db and Catchup with block
                # Block has already been verified to be in 2/3 consensus at this point
                self.client.raw_driver.revert()
                self.catchup_with_new_block(block)

            self.pending_sbcs.clear()

            # Request work. Use async / dealers to block until it's done?
            # Refresh sockets here
            # Turn this into a new message type
            work = await self.work_inbox.wait_for_next_batch_of_work()

            filtered_work = []
            for tx_batch in work:
                # Filter out None responses
                if tx_batch is None:
                    continue

                # Add the rest to a priority queue based on their timestamp
                heapq.heappush(filtered_work, (tx_batch.timestamp, tx_batch))

            # Execute work
            results = self.execute_work(filtered_work)

            # Package as SBCs
            sbcs_msg_blob = Message.get_message_packed_2(
                msg_type=MessageType.SUBBLOCK_CONTENDERS,
                contenders=[sb for sb in results]
            )

            # Send SBCs to masternodes
            tasks = []
            for k, v in self.parameters.get_masternode_sockets(service=ServiceType.BLOCK_AGGREGATOR):
                tasks.append(self.send_out(sbcs_msg_blob, v))

            await asyncio.gather(*tasks)

    def catchup_with_new_block(self, block):

            # if you're not in the signatures, run catchup
            # if you are in the signatures, commit db
        pass

    def execute_work(self, work):
        # Assume single threaded, single process for now.
        results = []
        i = 0

        while len(work) > 0:
            _, tx_batch = heapq.heappop(work)
            transactions = [tx for tx in tx_batch.transactions]

            now = Datetime._from_datetime(
                datetime.utcfromtimestamp(tx_batch.timestamp)
            )

            environment = {
                'block_hash': self.driver.latest_block_hash.hex(),
                'block_num': self.driver.latest_block_num,
                '__input_hash': tx_batch.inputHash, # Used for deterministic entropy for random games
                'now': now
            }

            # Each TX Batch is basically a subblock from this point of view and probably for the near future
            tx_data = []
            for transaction in transactions:
                # Deserialize Kwargs. Kwargs should be serialized JSON moving into the future for DX.
                kwargs = {}
                for entry in transaction.payload.kwargs.entries:
                    if entry.value.which() == 'fixedPoint':
                        kwargs[entry.key] = ContractingDecimal(entry.value.fixedPoint) # ContractingDecimal!
                    else:
                        kwargs[entry.key] = getattr(entry.value, entry.value.which())

                output = self.client.executor.execute(
                    sender=transaction.payload.sender.hex(),
                    contract_name=transaction.payload.contractName,
                    function_name=transaction.payload.functionName,
                    stamps=transaction.payload.stampsSupplied,
                    kwargs=kwargs,
                    environment=environment,
                    auto_commit=False
                )

                # Encode deltas into a Capnp struct
                deltas = [transaction_capnp.Delta.new_message(key=k, value=v) for k, v in output['writes'].items()]
                tx_output = transaction_capnp.TransactionData.new_message(
                        transaction=transaction,
                        status=output['status_code'],
                        state=deltas,
                        stampsUsed=output['stamps_used']
                    )

                tx_data.append(tx_output)

            sbc = self.build_sbc_from_work_results(
                input_hash=tx_batch.inputHash,
                results=tx_data,
                sb_num=i % self.parallelism
            )

            results.append(sbc)
            i += 1

        return results

    def build_sbc_from_work_results(self, input_hash, results, sb_num=0):
        merkle = merklize([r.to_bytes_packed() for r in results])
        proof = self.wallet.sign(merkle[0])

        merkle_tree = subblock_capnp.MerkleTree.new_message(
            leaves=[leaf for leaf in merkle],
            signature=proof
        )

        sbc = subblock_capnp.SubBlockContender.new_message(
            inputHash=input_hash,
            transactions=[r for r in results],
            merkleTree=merkle_tree,
            signer=self.wallet.verifying_key(),
            subBlockNum=sb_num,
            prevBlockHash=self.driver.latest_block_hash
        )

        self.pending_sbcs[merkle[0]] = proof

        return sbc
