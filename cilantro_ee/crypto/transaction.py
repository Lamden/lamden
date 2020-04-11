from cilantro_ee.crypto import wallet
from contracting import config
from cilantro_ee.storage import BlockchainDriver
from cilantro_ee.messages.capnp_impl import capnp_struct as schemas
import time
import os
import capnp

from contracting.db.encoder import encode, decode

transaction_capnp = capnp.load(os.path.dirname(schemas.__file__) + '/transaction.capnp')


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

        self.payload_bytes = self.payload.to_bytes_packed()
        self.signature = None

        self.tx_signed = False

    def sign(self, signing_key: bytes):
        # signs the payload binary
        self.signature = wallet._sign(signing_key, self.payload_bytes)
        self.tx_signed = True

    def serialize(self):
        if not self.tx_signed:
            return None

        self.struct.payload = self.payload
        self.struct.metadata.signature = self.signature
        self.struct.metadata.timestamp = int(time.time())

        return self.struct.to_bytes_packed()


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


class TransactionContractNameInvalid(TransactionException):
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
    if stamp_to_tau is None:
        stamp_to_tau = 1

    if balance * stamp_to_tau < tx.payload.stampsSupplied:
        print("bal -> {}, stamp2tau - > {}, txpayload -> {}".format(balance, stamp_to_tau, tx.payload.stampsSupplied))
        raise TransactionSenderTooFewStamps

    # Prevent people from sending their entire balances for free by checking if that is what they are doing.
    if tx.payload.contractName == 'currency' and tx.payload.functionName == 'transfer':
        kwargs = decode(tx.payload.kwargs)
        amount = kwargs.get('amount')

        # If you have less than 2 transactions worth of tau after trying to send your amount, fail.
        if ((balance - amount) * stamp_to_tau) / 3000 < 2:
            print(f'BAL IS: {((balance - amount) * stamp_to_tau) / 3000}')
            raise TransactionSenderTooFewStamps

    if tx.payload.contractName == 'submission' and tx.payload.functionName == 'submit_contract':
        kwargs = decode(tx.payload.kwargs)
        name = kwargs.get('name')

        if type(name) != str:
            raise TransactionContractNameInvalid

        if not name.startswith('con_'):
            raise TransactionContractNameInvalid

    driver.set_pending_nonce(tx.payload.processor, tx.payload.sender, pending_nonce)
