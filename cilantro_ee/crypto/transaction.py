from decimal import Decimal
from cilantro_ee.crypto import wallet
from cilantro_ee.crypto.pow import SHA3POW, SHA3POWBytes
from contracting import config
from cilantro_ee.storage import BlockchainDriver
from cilantro_ee.messages.capnp_impl import capnp_struct as schemas
import time
import os
import capnp

from contracting.db.encoder import encode, decode

transaction_capnp = capnp.load(os.path.dirname(schemas.__file__) + '/transaction.capnp')

NUMERIC_TYPES = {int, Decimal}
VALUE_TYPE_MAP = {
    str: 'text',
    bytes: 'data',
    bool: 'bool'
}


class TransactionBuilder:
    def __init__(self, sender, contract: str, function: str, kwargs: dict, stamps: int, processor: bytes,
                 nonce: int):

        # Stores variables in self for convenience
        self.sender = sender
        self.stamps = stamps
        self.processor = processor
        self.contract = contract
        self.function = function
        self.nonce = nonce
        self.kwargs = kwargs

        # Serializes all that it can on init
        self.struct = transaction_capnp.NewTransaction.new_message()
        self.payload = transaction_capnp.NewTransactionPayload.new_message()

        self.payload.sender = self.sender
        self.payload.processor = self.processor
        self.payload.stampsSupplied = self.stamps
        self.payload.contractName = self.contract
        self.payload.functionName = self.function
        self.payload.nonce = self.nonce

        self.payload.kwargs = encode(kwargs)

        # # Create a list of entries in Capnproto
        # self.payload.kwargs.init('entries', len(self.kwargs))
        #
        # # Enumerate through the Python dictionary and make sure to type cast when needed for Capnproto
        # for i, key in enumerate(self.kwargs):
        #     self.payload.kwargs.entries[i].key = key
        #     value, t = self.kwargs[key], type(self.kwargs[key])
        #
        #     # Represent numeric types as strings so we do not lose any precision due to floating point
        #     if t in NUMERIC_TYPES:
        #         self.payload.kwargs.entries[i].value.fixedPoint = str(value)
        #
        #     # This should be streamlined with explicit encodings for different types
        #     # For example, 32 byte strings -> UInt32
        #     else:
        #         assert t is not float, "Float types not allowed in kwargs. Used python's decimal.Decimal class instead"
        #         assert t in VALUE_TYPE_MAP, "value type {} with value {} not recognized in " \
        #                                     "types {}".format(t, self.kwargs[key], list(VALUE_TYPE_MAP.keys()))
        #         setattr(self.payload.kwargs.entries[i].value, VALUE_TYPE_MAP[t], value)

        self.payload_bytes = self.payload.to_bytes_packed()
        self.signature = None
        self.proof = None

        self.proof_generated = False
        self.tx_signed = False

    def sign(self, signing_key: bytes):
        # signs the payload binary
        self.signature = wallet._sign(signing_key, self.payload_bytes)
        self.tx_signed = True

    def generate_proof(self):
        #self.proof = pipehash.find_solution(self.epoch, self.payload_bytes, difficulty=self.proof_difficulty)
        self.proof = SHA3POWBytes.find(self.payload_bytes)
        self.proof_generated = True

    def serialize(self):
        if not self.tx_signed:
            return None

        if not self.proof_generated:
            self.generate_proof()

        self.struct.payload = self.payload
        self.struct.metadata.proof = self.proof
        self.struct.metadata.signature = self.signature
        self.struct.metadata.timestamp = int(time.time())

        return self.struct.to_bytes_packed()


# raghu todo this method is not used
def verify_packed_tx(sender, tx):
    try:
        unpacked = transaction_capnp.Transaction.from_bytes_packed(tx)
        msg = unpacked.payload

        proof = SHA3POW.check(msg, unpacked.metadata.proof.decode())
        sig = bytes.fromhex(unpacked.metadata.signature.decode())

        verified = wallet._verify(sender, msg, sig)
        return verified and proof
    except:
        return False


class TransactionException(Exception):
    pass


class TransactionSignatureInvalid(TransactionException):
    pass


class TransactionPOWProofInvalid(TransactionException):
    pass


class TransactionProcessorInvalid(TransactionException):
    pass


class TransactionTooManyPendingException(TransactionException):
    pass


class TransactionNonceInvalid(TransactionException):
    pass


class TransactionStampsNegative(TransactionException):
    pass


class TransactionSenderTooFewStamps(TransactionException):
    pass


def transaction_is_valid(tx: transaction_capnp.Transaction,
                         expected_processor: bytes,
                         driver: BlockchainDriver,
                         strict=True,
                         tx_per_block=15):
    # Validate Signature
    if not wallet._verify(tx.payload.sender,
                          tx.payload.as_builder().to_bytes_packed(),
                          tx.metadata.signature):
        raise TransactionSignatureInvalid

    # Validate Proof
    if not SHA3POWBytes.check(o=tx.payload.as_builder().to_bytes_packed(), proof=tx.metadata.proof):
        raise TransactionPOWProofInvalid

    # Check nonce processor is correct
    if tx.payload.processor != expected_processor:
        raise TransactionProcessorInvalid

    # Attempt to get the current block's pending nonce
    nonce = driver.get_nonce(tx.payload.processor, tx.payload.sender) or 0

    pending_nonce = driver.get_pending_nonce(tx.payload.processor, tx.payload.sender) or nonce

    if tx.payload.nonce - nonce > tx_per_block or pending_nonce - nonce >= tx_per_block:
        raise TransactionTooManyPendingException

    # Strict mode requires exact sequence matching (1, 2, 3, 4). This is for masternodes
    if strict:
        if tx.payload.nonce != pending_nonce:
            raise TransactionNonceInvalid
        pending_nonce += 1

    # However, some of those tx's might fail verification and never make it to delegates. Thus,
    # delegates shouldn't be as concerned. (1, 2, 4) should be valid for delegates.
    else:
        if tx.payload.nonce < pending_nonce:
            raise TransactionNonceInvalid
        pending_nonce = tx.payload.nonce + 1

    # Validate Stamps
    if tx.payload.stampsSupplied < 0:
        raise TransactionStampsNegative

    currency_contract = 'currency'
    balances_hash = 'balances'

    balances_key = '{}{}{}{}{}'.format(currency_contract,
                                       config.INDEX_SEPARATOR,
                                       balances_hash,
                                       config.DELIMITER,
                                       tx.payload.sender.hex())

    balance = driver.get(balances_key)
    if balance is None:
        balance = 0

    stamp_to_tau = driver.get_var('stamp_cost', 'S', ['value'])

    if balance * stamp_to_tau < tx.payload.stampsSupplied:
        raise TransactionSenderTooFewStamps

    driver.set_pending_nonce(tx.payload.processor, tx.payload.sender, pending_nonce)
