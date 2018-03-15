from cilantro.protocol.wallets import ED25519Wallet
from cilantro.logger.base import get_logger
from cilantro import Constants
import asyncio
from cilantro.models import StandardTransaction, Message
from cilantro.models.consensus import MerkleTree, MerkleSignature, BlockContender
from cilantro.models.message.message import MODEL_TYPES # TODO -- find a better home for these constants
from cilantro.db.delegate.transaction_queue_driver import TransactionQueueDriver
from cilantro.protocol.interpreters import VanillaInterpreter

from cilantro.protocol.reactor import NetworkReactor
# if sys.platform != 'win32':
#     import uvloop
#     asyncio.set_event_loop_policy(uvloop.EventLoopPolicy)

import time

"""
    Delegates

    Delegates are the "miners" of the Cilantro blockchain in that they opportunistically bundle up transaction into 
    blocks and are rewarded with TAU for their actions. They receive approved transaction from delegates and broadcast
    blocks based on a 1 second or 10,000 transaction limit per block. They should be able to connect/drop from the 
    network seamlessly as well as coordinate blocks amongst themselves.
    
     Delegate logic:   
        Step 1) Delegate takes 10k transaction from witness and forms a block
        Step 2) Block propagates across the network to other delegates
        Step 3) Delegates pass around in memory DB hash to confirm they have the same blockchain state
        Step 4) Next block is mined and process repeats

        zmq pattern: subscribers (delegates) need to be able to communicate with one another. this can be achieved via
        a push/pull pattern where all delegates push their state to sink that pulls them in, but this is centralized.
        another option is to use ZMQ stream to have the tcp sockets talk to one another outside zmq
"""

class Delegate:
    def __init__(self, url, delegates: dict, signing_key):
        self.port = int(url[-4:])
        self.log = get_logger("Delegate-{}".format(self.port), auto_bg_val=self.port)
        self.url = url

        self.log.info("Spinning up delegate /w url={}".format(self.url))

        self.delegates = delegates
        # Remove self from delegates hash
        del self.delegates[url]
        self.log.debug("delegates (excluding self): {}".format(self.delegates))
        self.signing_key = signing_key

        # consensus variables
        self.merkle = None
        self.signature = b'too soon bro'
        self.signatures, self.failed_signatures = {}, {}

        # Setup reactor, subscribe to witness
        self.reactor = NetworkReactor(self)
        witness_url = 'tcp://127.0.0.1:{}'.format(Constants.Witness.PubPort)
        self.reactor.add_sub(url=witness_url, callback='handle_message')

        # Sub to other delegates
        for d_url in self.delegates:
            self.reactor.add_sub(url=d_url, callback='handle_message')

        # Publish on our own URL
        self.reactor.add_pub(url=self.url)

        # Queue + Interpreter
        self.queue = TransactionQueueDriver(db=str(self.port)[-1:])
        self.interpreter = VanillaInterpreter(port=str(self.port))

        # Flush queue on boot
        self.log.debug("Delegate flushing queue on boot")
        self.queue.dequeue_all()

        # Notify reactor that this node is ready to flex
        self.reactor.notify_ready()

    def handle_message(self, msg):
        # self.log.debug("Got message: {}".format(msg))
        m = None
        try:
            m = Message.from_bytes(msg)
        except Exception as e:
            self.log.error("Error deserializing msg: {}".format(e))

        # Route m
        if m.type == MODEL_TYPES[StandardTransaction.name]['id']:
            self.handle_tx(m.payload)
        elif m.type == MODEL_TYPES[MerkleSignature.name]['id']:
            self.handle_sig(m.payload)
        else:
            self.log.error("Got message of unknown type: {}".format(m.type))
            raise ValueError("Got message of unknown type: {}".format(m.type))

    def handle_tx(self, tx_binary):
        self.log.debug("Unpacking standard tx")
        tx = None

        # Deserialize tx
        try:
            tx = StandardTransaction.from_bytes(tx_binary)
        except Exception as e:
            self.log.error("Error unpacking standard transaction: {}".format(e))

        # Feed tx to interpreter
        try:
            self.log.debug("Interpreting standard tx")
            self.interpreter.interpret_transaction(tx)
        except Exception as e:
            self.log.error("Error interpreting tx: {}".format(e))

        self.log.debug("Successfully interpreted tx...adding it to queue")
        self.queue.enqueue_transaction(tx.serialize())

        if self.queue.queue_size() >= 4:
            self.gather_consensus()

    def handle_sig(self, sig_payload):
        sig = MerkleSignature.from_bytes(sig_payload)
        self.log.debug("Received signature with data {}".format(sig._data))

        # Sanity check (for debugging purposes)
        if (sig.sender in self.signatures) or (sig.sender in self.failed_signatures):
            self.log.error("OH NO -- this delegate already has a signature from {}".format(sig.sender))
            return

        if sig.verify(self.merkle.hash_of_nodes(), self.delegates[sig.sender]):
            self.log.debug("Signature validated from sender {}".format(sig.sender))
            self.signatures[sig.sender] = sig
        else:
            self.log.warning("!!! Signature NOT validated from sender {}".format(sig.sender))
            self.failed_signatures[sig.sender] = sig

        self.log.debug("Number of sigs: {}".format(len(self.signatures)))

        if len(self.signatures) > (len(self.delegates) + 1) // 2:
            self.log.critical("We in consensus bruh!!! sigs={}".format(self.signatures))
            # TODO -- successful consensus logic

    def gather_consensus(self):
        self.log.debug("Starting consesnsus with peers: {}".format(self.delegates))

        # Merkle-ize tx and sign
        tx = self.queue.dequeue_all()
        self.merkle = MerkleTree(tx)
        self.signature = ED25519Wallet.sign(self.signing_key, self.merkle.hash_of_nodes())
        self.log.critical('Signature for merkle is {}'.format(self.signature))

        # Create merkle signature message
        merkle_sig = MerkleSignature.from_fields(sig_hex=self.signature, timestamp='now', sender=self.url)
        sig_msg = Message.create(MerkleSignature, merkle_sig.serialize())

        self.log.info("Broadcasting signatures...")
        self.reactor.pub(url=self.url, data=sig_msg.serialize())
        self.log.info("Done broadcasting signatures.")



