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

# need delegate communication class to describe events
#  all currently known hand-shakes of block making
#  get # of txns
#  move to block state. may skip some due to low vol of txns there.
# need block state events
#    for 4 blocks:
#       blocks in 1 and 2 stages, just do io (no cpu - to make sure cpu is available for other proceses)
#                just txns from witness and drop it in queue  - may keep a count of # of txns


class SubBlockBuilder:
    def __init__(self, signing_key, witness_list, url, sbb_index):
        self.log = get_logger("SubBlockBuilder_{}".format(sb_index))
        # Comment out below for more granularity in debugging
        # self.log.setLevel(logging.INFO)

        #self.log.important("SubBlockBuilder started with url {}".format(url))

        # Register signal handler to teardown
        signal.signal(signal.SIGTERM, self._signal_teardown)

        # need to revisit this when threading strategy is clear
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

        self.signing_key = signing_key
        # witness_list should be comma separated list of ip:vk  
        self.witness_table = self._parse_witness_list(witness_list)
        self.url = url
        self.sbb_index = sbb_index
        self.block_num = (int) sbb_index / 16       # hard code this for now
        self.sub_block_num = (int) sb_index % 16
        self.num_txs = 0
        self.num_sub_blocks = 0
        self.tasks = []

        #SenecaInterpreter connect with BlockManager (parent process that spawned this one)
        self.context = zmq.asyncio.Context()
        self.socket = self.context.socket(zmq.PAIR)  # For communication with main process
        self.socket.connect(self.url)

        # do we need this still? or do we move it to a util methods
        self.verifying_key = wallet.get_vk(self.signing_key)
        skg = SigningKey(seed=bytes.fromhex(sk))
        self.vk = skg.verify_key.encode().hex()
        self.public_key = self.vk2pk(self.vk)
        self.private_key = crypto_sign_ed25519_sk_to_curve25519(skg._signing_key).hex()
        priv = PrivateKey(bytes.fromhex(self.private_key))
        publ = priv.public_key
        self.public_key = public_key = encode(publ._public_key)
        self.secret = secret_key = encode(priv._private_key)

        self.pending_txs = LinkedHashTable()
        self.interpreter = SenecaInterpreter()
        self._recently_seen = CappedSet(max_size=DUPE_TABLE_SIZE)

        try:
            self._subscribe_to_witnesses()
            # start event loop and start listening witness sockets as well as mgr
            self.run_loop_second_time()
        except Exception as e:
            err_msg = '\n' + '!' * 64 + '\nSBB terminating with exception:\n' + str(traceback.format_exc())
            err_msg += '\n' + '!' * 64 + '\n'
            self.log.error(err_msg)
        finally:
            self._teardown()

    def _parse_witness_list(self, witness_list):
        witnesses = witness_list.split(",")
        for witness in witnesses:
          ip, vk = witness.split(":", 1)
          self.witness_table[ip] = []
          self.witness_table[ip].append(vk)
          
    def _subscribe_to_witnesses(self):
        for ip, value in self.witness_table:
            witness_vk = value[0]
            url = "{}:{}".format(ip, PUB_SUB_PORT)
            socket = self._add_sub(
                                   url=url,
                                   filter=str(WITNESS_DELEGATE_FILTER),
                                   vk=witness_vk)
            self.witness_table[ip].append(socket)
            self.tasks.append(self._listen_to_witness(socket, url))
            self.log.debug("Added sub connection to witness at ip:{} socket:{}"
                           ."filter {}"
                           .format(ip, witness_vk, WITNESS_DELEGATE_FILTER))

    def run_loop_forever(self):
        self.tasks.append(self._listen_to_block_manager())
        self.loop.run_until_complete(asyncio.gather(*tasks))

    async def _listen_to_block_manager(self):
        try:
            self.log.debug(
               "Sub-block builder {} listening to Block-manager process at {}"
               .format(self.sbb_index, self.url))
            while True:
                cmd_bin = await self.socket.recv()
                self.log.debug("Got cmd from BM: {}".format(cmd_bin))

                # need to change logic here based on our communication protocols
                if cmd_bin == KILL_SIG:
                    self.log.debug("Sub-block builder {} got kill signal"
                    .format(self.sbb_index))
                    self._teardown()
                    return

                if cmd_bin == MAKE_SUBTREE:
                    # self._interpret = 1  ?
                    return

                if cmd_bin == SEND_NUM_TXS:
                    # send back number of txs pending so it can skip this block if too low

                if cmd_bin == CANCEL_SUBTREE:
                    if self._interpret:
                        self._interpret = 0


        except asyncio.CancelledError:
            self.log.warning("Builder _recv_messages task canceled externally")


    # async def recv_multipart(self, socket, callback_fn: types.MethodType, ignore_first_frame=False):
    async def _listen_to_witness(self, socket, url, ignore_first_frame = True):
        self.log.debug("Sub-block builder {} listening to witness at {}"
                       .format(self.sbb_index, url))
        while True:
            try:
                msg = await socket.recv_multipart()
            except asyncio.CancelledError:
                self.log.debug("Socket at witness {} cancelled".format(url))
                socket.close()
                break

            if ignore_first_frame:
                header = None
            else:
                assert len(msg) == 2,
                       "Expected 2 frames (header, envelope) but got {}"
                       .format(msg)
                header = msg[0].decode()

            env_binary = msg[-1]
            env = self._validate_envelope(envelope_binary=env_binary,
                                          header=header)

            if not env:
                continue

            self._recently_seen.add(env.meta.uuid)
            tx = envelope.message
            self.pending_txs.append(Hasher.hash(tx.transaction), tx)
            # update num_txs and num_sub_blocks


    async def _interpret_next_subtree(self, num_of_batches = 1):
        self.log.debug("Starting to make a new sub-block {} for block {}"
                       .format(self.sub_block_num, self.block_num))
        # get next batch of txns ??  still need to decide whether to unpack a bag or check for end of txn batch
        while(num_of_batches > 0):
            txn = self.pending_txs.popleft()
            if txn == end_of_batch:
                num_of_batches = num_of_batches - 1
            else:
                self.interpreter.interpret(txn)  # this is a blocking call. either async or threads??
            if not self._interpret:         # do we need abort??
                self.interpreter.flush(update_state=False)
                return;

        # Merkle-ize transaction queue and create signed merkle hash
        all_tx = self.interpreter.queue_binary
        self.merkle = MerkleTree.from_raw_transactions(all_tx)
        self.signature = wallet.sign(self.signing_key, self.merkle.root)

        # Create merkle signature message and publish it
        merkle_sig = MerkleSignature.create(sig_hex=self.signature,
                                            timestamp='now',
                                            sender=self.verifying_key)
        self.send_signature(merkle_sig)  # send signature to block manager


    def send_signature(self, merkle_sig):
        self.socket.send(merkle_sig.serialize())


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

    # could this be as part of socket/communication utils ??
    def _secure_socket(self, sock, curve_serverkey=None):
        sock.curve_secretkey = self.secret
        sock.curve_publickey = self.public_key
        if curve_serverkey:
            sock.curve_serverkey = curve_serverkey
        else:
            sock.curve_server = True
        return sock

    # could this be as part of zmq utils ??
    def _add_sub(self, url: str, filter: str, vk: str):
        assert isinstance(filter, str), "'filter' arg must be a string"

        self.log.notice("Creating subscriber socket to {}".format(url))
        curve_serverkey = self.vk2pk(vk)
        socket = self._secure_socket(
                                     self.context.socket(socket_type=zmq.SUB),
                                     curve_serverkey=curve_serverkey)
        socket.connect(url)
        socket.setsockopt(zmq.SUBSCRIBE, filter.encode())
        return socket

