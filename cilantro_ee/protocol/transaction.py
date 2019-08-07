from decimal import Decimal
from cilantro_ee.protocol import wallet
from cilantro_ee.protocol.pow import SHA3POW, SHA3POWBytes
from contracting import config
from cilantro_ee.storage.state import MetaDataStorage
from cilantro_ee.messages import capnp as schemas
import time
import os
import capnp

transaction_capnp = capnp.load(os.path.dirname(schemas.__file__) + '/transaction.capnp')

NUMERIC_TYPES = {int, Decimal}
VALUE_TYPE_MAP = {
    str: 'text',
    bytes: 'data',
    bool: 'bool'
}


class TransactionWrapper:
    def __init__(self, struct: transaction_capnp.Transaction):
        self.struct = struct

    def is_signed(self) -> bool:
        return wallet._verify(vk=self.struct.payload.sender,
                              msg=self.struct.payload,
                              signature=self.struct.metadata.signature)

    def is_proven(self) -> bool:
        return SHA3POW.check(self.struct.payload, self.struct.metadata.proof)

    def nonce_is_correct(self, driver) -> bool:
        pass

    def is_completely_valid(self, driver):
        return self.is_signed() and self.is_proven() and self.nonce_is_correct(driver)

    def arguments_to_py_dict(self) -> dict:
        kwargs = {}
        for entry in self.struct.payload.kwargs.entries:
            if entry.value.which() == 'fixedPoint':
                kwargs[entry.key] = Decimal(entry.value.fixedPoint)
            else:
                kwargs[entry.key] = getattr(entry.value, entry.value.which())
        return kwargs


class TransactionBuilder:
    def __init__(self, sender, contract: str, function: str, kwargs: dict, stamps: int, processor: bytes, nonce: int):
        # Stores variables in self for convenience
        self.sender = sender
        self.stamps = stamps
        self.processor = processor
        self.contract = contract
        self.function = function
        self.nonce = nonce
        self.kwargs = kwargs

        # Serializes all that it can on init
        self.struct = transaction_capnp.Transaction.new_message()
        self.payload = transaction_capnp.TransactionPayload.new_message()

        self.payload.sender = self.sender
        self.payload.processor = self.processor
        self.payload.stampsSupplied = self.stamps
        self.payload.contractName = self.contract
        self.payload.functionName = self.function
        self.payload.nonce = self.nonce

        # Create a list of entries in Capnproto
        self.payload.kwargs.init('entries', len(self.kwargs))

        # Enumerate through the Python dictionary and make sure to type cast when needed for Capnproto
        for i, key in enumerate(self.kwargs):
            self.payload.kwargs.entries[i].key = key
            value, t = self.kwargs[key], type(self.kwargs[key])

            # Represent numeric types as strings so we do not lose any precision due to floating point
            if t in NUMERIC_TYPES:
                self.payload.kwargs.entries[i].value.fixedPoint = str(value)

            # This should be streamlined with explicit encodings for different types
            # For example, 32 byte strings -> UInt32
            else:
                assert t is not float, "Float types not allowed in kwargs. Used python's decimal.Decimal class instead"
                assert t in VALUE_TYPE_MAP, "value type {} with value {} not recognized in " \
                                            "types {}".format(t, self.kwargs[key], list(VALUE_TYPE_MAP.keys()))
                setattr(self.payload.kwargs.entries[i].value, VALUE_TYPE_MAP[t], value)

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
        self.proof = SHA3POW.find(self.payload_bytes)[0]
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

    def as_struct(self):
        if not self.tx_signed:
            return None

        if not self.proof_generated:
            self.generate_proof()

        return transaction_capnp.Transaction.new_message(
            metadata=self.struct.metadata,
            payload=self.struct.payload
        )


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


def transaction_is_valid(tx: transaction_capnp.Transaction, expected_processor: bytes,
                         driver: MetaDataStorage):
    # Check nonce processor is correct
    if tx.payload.processor != expected_processor:
        return False

    pending_nonce = driver.get_pending_nonce(tx.payload.processor, tx.payload.sender)
    if pending_nonce is None:
        pending_nonce = 0

    if tx.payload.nonce != pending_nonce:
        return False

    pending_nonce += 1
    driver.set_pending_nonce(tx.payload.processor, tx.payload.sender, pending_nonce)

    if not wallet._verify(tx.payload.sender,
                          tx.payload.as_builder().to_bytes_packed(),
                          tx.metadata.signature):
        return False

    if not SHA3POWBytes.check(tx.payload.as_builder().to_bytes_packed(),
                              tx.metadata.proof):
        return False

    if tx.payload.stampsSupplied > 0:
        currency_contract = 'currency'
        balances_hash = 'balances'

        balances_key = '{}{}{}{}{}'.format(currency_contract,
                                           config.INDEX_SEPARATOR,
                                           balances_hash,
                                           config.DELIMITER,
                                           tx.payload.sender.hex())

        balance = driver.get(balances_key) or 0

        if balance < tx.payload.stampsSupplied:
            return False

    return True
