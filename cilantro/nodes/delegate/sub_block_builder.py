"""
    SubBlockBuilder

    Conceptually Sub Block could form whole block or part of block. This lets us scale things horizontally.
    Each of this builder will be started on a separate process and will assume BlockManager would be 
    responsible to resolve db conflicts (due to ordering of these sub-blocks at block level) and 
    send resolved subtree to master (and other delegates).
    it will send its vote on other subblocks to master directly.
    
    We will make each SubBlockBuilder responsible for one master and so in our case, we will have 64 processes,
    each producing a sub-block. We can form one block with 8/16 sub-blocks so we will have 8/4 independent blocks.
    1 master    -> 1 subblcok
    2 subblocks -> 1 subtree
    8 subtrees  -> 1 block
    64 masters -> 64 sub-blocks -> 32 subtrees -> 4 blocks
    
    SubBlockBuilder
      Input: set of witnesses that provide transactions from a single master
             need to use proxies for zmq communication as witnesses are dynamically rotated to help different masters
             connection port to BlockManager
      0. Opens a subscribe connection to witness pool (thread1)
         just put them in a queue 
      1. Initialization: establish connections to blockmgr (the main process that launched this one)
         when asked to start making a new subblock (blkMgr)
         2. pull next batch from queue (Seneca interface and cost of db access is included here)
         3. Failed contracts have to be in pending state to be resolved
         4. if some failed contracts, resolve or reject them or push them to next block (communication cost to BlkMgr here)
         5. Also BlockMgr may send in new failures (communication cost)
         6. Make and send subblock to blockMgr
"""

# need to clean this up - this is a dirty version of trying to separate out a sub-block builder in the old code
import asyncio, os, logging
import zmq.asyncio
from cilantro.protocol.structures import MerkleTree
from cilantro.protocol import wallet
from cilantro.messages.consensus.merkle_signature import MerkleSignature
from cilantro.logger import get_logger
from cilantro.protocol.reactor.executor import Executor
from cilantro.messages.reactor.reactor_command import ReactorCommand
from cilantro.protocol.overlay.dht import DHT
from cilantro.protocol.overlay.node import Node
from cilantro.protocol.overlay.utils import digest
from cilantro.protocol.structures import CappedDict
from cilantro.utils import IPUtils
from cilantro.constants.zmq_filters import DELEGATE_DELEGATE_FILTER, WITNESS_DELEGATE_FILTER
import signal, sys
from cilantro.protocol.states.state import StateInput
from cilantro.constants.overlay_network import ALPHA, KSIZE, MAX_PEERS
import inspect
from cilantro.storage.blocks import BlockStorageDriver
from cilantro.messages.transaction.ordering import OrderingContainer
from cilantro.constants.nodes import BLOCK_SIZE
from cilantro.protocol.states.decorators import input, enter_from_any, exit_to_any, exit_to, enter_from
from zmq.utils.z85 import decode, encode
from nacl.public import PrivateKey, PublicKey
from nacl.signing import SigningKey, VerifyKey
from nacl.bindings import crypto_sign_ed25519_sk_to_curve25519
from cilantro.storage.db import VKBook
from collections import defaultdict
from cilantro.constants.protocol import DUPE_TABLE_SIZE
from cilantro.protocol.interpreter import SenecaInterpreter
from cilantro.messages.envelope.envelope import Envelope
from cilantro.protocol.structures import CappedSet
from cilantro.protocol.structures.linked_hashtable import LinkedHashTable
from typing import Union
from cilantro.constants.ports import PUB_SUB_PORT
from cilantro.utils.hasher import Hasher
import time

import types
import uvloop
import traceback
asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())

INITIAL_SIG = b'Start'
CHILD_RDY_SIG = b'SubBlockBuilder Process Ready'
KILL_SIG = b'DIE'
MAKE_SUBTREE = b'Make a new subtree'
DONE_SUBTREE = b'Done making subtree'
CANCEL_SUBTREE = b'Cancel making subtree'
MERKLE_SIG = b'MS '
SUB_TO_WITNESSES = b'Subscribe to witness set'

class SubBlockBuilder:
    def __init__(self, url, sk, port, name='SubBlockBuilder'):
        self.log = get_logger("{}.SubBlockBuilder".format(name))
        self.log.important("SubBlockBuilder started with url {}".format(url))
        self.url = url

        # Comment out below for more granularity in debugging
        # self.log.setLevel(logging.INFO)

        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

        # Register signal handler to teardown
        signal.signal(signal.SIGTERM, self._signal_teardown)
        self.state = INITIAL_SIG

        self.context = zmq.asyncio.Context()
        self.socket = self.context.socket(zmq.PAIR)  # For communication with main process
        self.socket.connect(self.url)

        self.signing_key = sk
        self.verifying_key = wallet.get_vk(self.signing_key)
        skg = SigningKey(seed=bytes.fromhex(sk))
        self.vk = skg.verify_key.encode().hex()
        self.public_key = self.vk2pk(self.vk)
        self.private_key = crypto_sign_ed25519_sk_to_curve25519(skg._signing_key).hex()
        priv = PrivateKey(bytes.fromhex(self.private_key))
        publ = priv.public_key
        self.public_key = public_key = encode(publ._public_key)
        self.secret = secret_key = encode(priv._private_key)

        self.urls = []
        self.subs = defaultdict(dict)  # Subscriber socket
        # crawler_port = kwargs.get('port') or os.getenv('PORT', 30001)

        # self.ironhouse = Ironhouse(auth_port=port+3, *args, **kwargs)
        # self.ip = // raghu
        self.pending_txs = LinkedHashTable()
        self.interpreter = SenecaInterpreter()
        self._recently_seen = CappedSet(max_size=DUPE_TABLE_SIZE)
        self._interpret = 0
        # self.current_hash = BlockStorageDriver.get_latest_block_hash()
        self.log.important("raghu started a separate process")
        self.log.important("Subblock builder notifying main proc of ready")

        try:
            #self.socket.send(CHILD_RDY_SIG)
            #loop = asyncio.new_event_loop()
            #asyncio.set_event_loop(loop)
            #loop.run_until_complete(self._recv_messages())
            self.log.important("raghu come out of first loop")
            #loop.close()
            #asyncio.set_event_loop(self.loop)
            time.sleep(2)
            self.sub_to_witnesses()
            self.log.important("raghu starting second loop now witnesses are subscribed")
            self.run_loop_second_time()
            #if self.state == SUB_TO_WITNESSES:
                #self.log.important("raghu starting second loop now witnesses are subscribed")
                # self.run_loop_second_time()
        except Exception as e:
            err_msg = '\n' + '!' * 64 + '\nDeamon Loop terminating with exception:\n' + str(traceback.format_exc())
            err_msg += '\n' + '!' * 64 + '\n'
            self.log.error(err_msg)
        finally:
            self._teardown()

    def run_loop_second_time(self):
        # tasks = []
        # for url in self.urls:
            # self.log.important("raghu adding future for {}".format(url))
            # tasks.append(asyncio.ensure_future(self.recv_multipart(self.subs[url]['socket'], self._recv_pub_env, True)))
        # tasks.append(asyncio.ensure_future(self._recv_messages()))
        # tasks = []
        # for url in self.urls:
            # self.log.important("raghu adding future for {}".format(url))
            # tasks.append(asyncio.ensure_future(self.recv_multipart(self.subs[url]['socket'], self._recv_pub_env, True)))
        # tasks.append(asyncio.ensure_future(self._recv_messages()))
        # group1 = asyncio.gather(*[self.recv_txs(i) for i self.urls])
        #group = asyncio.gather(self._recv_messages(), group1)
        #group = asyncio.gather(tasks)
        i = 0
        s0 = None
        s1 = None
        for url in self.urls:
            if i == 0:
                s0 = self.subs[url]['socket']
                i = i + 1
                self.log.important("raghu set first socket {}".format(s0))
            else:
                s1 = self.subs[url]['socket']
                self.log.important("raghu set second socket {}".format(s1))

        group = asyncio.gather(self._recv_messages(), self.recv_txs(s0), self.recv_txs(s1))
        
        self.log.important("raghu starting second loop")
        self.loop.run_until_complete(group)
        self.log.important("raghu done second loop")

    def sub_to_witnesses(self):
        # Sub to TESTNET_WITNESSES
        i = 2
        for witness_vk in VKBook.get_witnesses():
            self.log.important("Raghu Added sub connection to {} with {}".format(witness_vk, WITNESS_DELEGATE_FILTER))
            url = "tcp://172.29.5.{}:{}".format(i, PUB_SUB_PORT)
            i = i + 1
            self.add_sub(url=url, filter=str(WITNESS_DELEGATE_FILTER), vk=witness_vk)
        time.sleep(2)

    async def _recv_messages(self):
        try:
            self.log.important("-- Builder proc listening to main proc on PAIR Socket at {} --".format(self.url))
            while True:
                self.log.important("subblock builder awaiting for command from main thread...")
                cmd_bin = await self.socket.recv()
                self.log.important("rraghu Got cmd from queue: {}".format(cmd_bin))

                if cmd_bin == KILL_SIG:
                    self.log.important("rraghu Builder Process got kill signal from main proc")
                    # self._teardown()
                    self.state = KILL_SIG
                    return

                if cmd_bin == SUB_TO_WITNESSES:
                    self.log.important("rraghu Builder Process to sub to witnesses ... ")
                    #await self.sub_to_witnesses()
                    self.state = SUB_TO_WITNESSES
                    # return

                if cmd_bin == MAKE_SUBTREE:
                    self.log.important("rraghu Building a new subtree ... ")
                    self._interpret = 1
                    await self._interpret_next_subtree()
                    # return

                if cmd_bin == CANCEL_SUBTREE:
                    self.log.important("rraghu Builder Process canceling subtree ... ")
                    if self._interpret:
                        self._interpret = 0
                        self.send_done_tree()


        except asyncio.CancelledError:
            self.log.warning("Builder _recv_messages task canceled externally")

    async def recv_txs(self, socket):
        await self.recv_multipart(socket, self._recv_pub_env, True)

    async def recv_multipart(self, socket, callback_fn: types.MethodType, ignore_first_frame=False):
        self.log.important("--- Starting recv on socket {} with callback_fn {} ---".format(socket, callback_fn))
        while True:
            self.log.spam("waiting for multipart msg...")

            try:
                # self.log.important("raghu waiting at socket for data ...");
                msg = await socket.recv_multipart()
                # self.log.important("raghu read sub data from socket ...");
            except asyncio.CancelledError:
                self.log.important("Socket cancelled: {}".format(socket))
                socket.close()
                break

            # self.log.important("Got multipart msg len: {}".format(len(msg)))
            #self.log.important("Got multipart msg len: {}: {}".format(len(msg), msg))

            if ignore_first_frame:
                header = None
            else:
                assert len(msg) == 2, "Expected 2 frames (header, envelope) but got {}".format(msg)
                header = msg[0].decode()

            env_binary = msg[-1]
            env = self._validate_envelope(envelope_binary=env_binary, header=header)

            if not env:
                continue

            self._recently_seen.add(env.meta.uuid)
            callback_fn(header=header, envelope=env)

    def _recv_pub_env(self, header: str, envelope: Envelope):
        # self.log.important("raghu Recv'd pub envelope with header {} and env {}".format(header, envelope))
        tx = envelope.message
        self.pending_txs.append(Hasher.hash(tx.transaction), tx)
        #self.call_on_mp(callback=StateInput.INPUT, envelope_binary=envelope.serialize())

    async def _interpret_next_subtree(self):
        self.log.important("rraghu starting to make a new subtree ... ")
        # asyncio.sleep(3)
        # self.log.important("rraghu done making new subtree ... ")
        # return
        while(len(self.pending_txs) < BLOCK_SIZE):
            await asyncio.sleep(1)
        num_to_pop = min(len(self.pending_txs), BLOCK_SIZE)
        self.log.important("raghu Flushing {} txs from total {} pending txs".format(num_to_pop, len(self.pending_txs)))
        for _ in range(num_to_pop):
            if self._interpret:
                self.interpret_tx(self.pending_txs.popleft())

        if not self._interpret:
            self.interpreter.flush(update_state=False)
            return;
        # Merkle-ize transaction queue and create signed merkle hash
        all_tx = self.interpreter.queue_binary
        # self.log.debugv("sbb got tx from interpreter queue: {}".format(all_tx))
        self.merkle = MerkleTree.from_raw_transactions(all_tx)
        self.log.debugv("sbb got merkle hash {}".format(self.merkle.root_as_hex))
        self.signature = wallet.sign(self.signing_key, self.merkle.root)

        # Create merkle signature message and publish it
        merkle_sig = MerkleSignature.create(sig_hex=self.signature, timestamp='now',
                                            sender=self.verifying_key)
        self.send_done_tree()
        self.log.debugv("Sending signature {}".format(self.signature))
        # signal here to transition to consensus and then
        self.send_signature(merkle_sig)

    def send_done_tree(self):
        self.socket.send(DONE_SUBTREE)

    def send_signature(self, merkle_sig):
        self.socket.send(merkle_sig.serialize())
        self.log.important("rraghu sent merkle signature ... ")

    def interpret_tx(self, tx: OrderingContainer):
        self.interpreter.interpret(tx)
        self.log.debugv("Current size of transaction queue: {}".format(len(self.interpreter.queue)))

        # raghu - todo - move this to one function up
        if self.interpreter.queue_size == BLOCK_SIZE:
            self.log.success("Consensus time! sbb has {} tx in queue.".format(self.interpreter.queue_size))
            # self.parent.transition(DelegateConsensusState)
            # raghu - need to send this for consensus making
            return

        elif self.interpreter.queue_size > BLOCK_SIZE:
            self.log.fatal("sbb exceeded max queue size! How did this happen!!!")
            raise Exception("sbb exceeded max queue size! How did this happen!!!")

        else:
            self.log.debug("Not consensus time yet, queue is only size {}/{}"
                           .format(self.interpreter.queue_size, BLOCK_SIZE))

    def _validate_envelope(self, envelope_binary: bytes, header: str) -> Union[None, Envelope]:
        # TODO return/raise custom exceptions in this instead of just logging stuff and returning none

        # Deserialize envelope
        env = None
        try:
            env = Envelope.from_bytes(envelope_binary)
        except Exception as e:
            self.log.error("Error deserializing envelope: {}".format(e))
            return None

        # Check seal
        if not env.verify_seal():
            self.log.error("Seal could not be verified for envelope {}".format(env))
            return None

        # If header is not none (meaning this is a ROUTE msg with an ID frame), then verify that the ID frame is
        # the same as the vk on the seal
        if header and (header != env.seal.verifying_key):
            self.log.error("Header frame {} does not match seal's vk {}\nfor envelope {}"
                           .format(header, env.seal.verifying_key, env))
            return None

        # Make sure we haven't seen this message before
        if env.meta.uuid in self._recently_seen:
            self.log.debug("Duplicate envelope detect with UUID {}. Ignoring.".format(env.meta.uuid))
            return None

        # TODO -- checks timestamp to ensure this envelope is recv'd in a somewhat reasonable time (within N seconds)

        # If none of the above checks above return None, this envelope should be good
        return env

    def _signal_teardown(self, signal, frame):
        self.log.important("Builder process got kill signal!")
        self._teardown()

    def _teardown(self):
        """
        Close sockets. Teardown executors. Close Event Loop.
        """
        #self.log.info("[DEAMON PROC] Tearing down Reactor Builder process")

        self.log.warning("Closing pair socket")
        self.socket.close()

        #self.log.warning("Tearing down executors")
        #for e in self.executors.values():
            #e.teardown()

        self.log.warning("Closing event loop")
        self.loop.call_soon_threadsafe(self.loop.stop)

    def vk2pk(self, vk):
        return encode(VerifyKey(bytes.fromhex(vk)).to_curve25519_public_key()._public_key)

    def secure_socket(self, sock, curve_serverkey=None):
        sock.curve_secretkey = self.secret
        sock.curve_publickey = self.public_key
        if curve_serverkey:
            sock.curve_serverkey = curve_serverkey
        else: sock.curve_server = True
        return sock

    def add_sub(self, url: str, filter: str, vk: str):
        assert isinstance(filter, str), "'filter' arg must be a string"
        # assert vk != self.ironhouse.vk, "Cannot subscribe to your own VK"

        self.log.important("raghu url {}".format(url))
        # url = "tcp://{}:{}".format(vk, PUB_SUB_PORT)
        self.urls.append(url)
        # self.log.important("raghu url2 {}".format(url))
        if url not in self.subs:
            self.log.notice("Creating subscriber socket to {}".format(url))

            curve_serverkey = self.vk2pk(vk)
            self.subs[url]['socket'] = socket = self.secure_socket(
                self.context.socket(socket_type=zmq.SUB),
                curve_serverkey=curve_serverkey)
            self.subs[url]['filters'] = []

            socket.connect(url)

        if filter not in self.subs[url]['filters']:
            self.log.debugv("Adding filter {} to sub socket at url {}".format(filter, url))
            self.subs[url]['filters'].append(filter)
            self.subs[url]['socket'].setsockopt(zmq.SUBSCRIBE, filter.encode())

        # self.loop.run_until_complete(self.recv_multipart(self.subs[url]['socket'], self._recv_pub_env, True))
        # self.loop2.append(loop)
        #loop.run_until_complete(self.recv_multipart(self.subs[url]['socket'], self._recv_pub_env, True))
