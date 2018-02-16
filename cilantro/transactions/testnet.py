from cilantro.transactions import Transaction
from cilantro.wallets import Wallet, ED25519Wallet
from cilantro.proofs.pow import POW

class TestNetTransaction(Transaction):
    # support stamp transactions, vote transactions, etc.
    payload_format = {
        'payload' : None,
        'metadata' : {
            'signature' : None,
            'proof' : None
        }
    }

    TX = 't'
    STAMP = 's'
    VOTE = 'v'
    SWAP = 'a'
    REDEEM = 'r'

    @staticmethod
    def validate_tx_fields(tx: dict) -> bool:
        """
        Attempts to validate the transaction fields, and throws and error if any fields are missing. If
        the fields are valid, this method returns true
        :param tx: A transaction dictionary, assumed to be in the same form as it would be in a user's initial POST
        request to Masternode
        :return: True if the transaction fields are valid
        :raises: An exception if an invalid or missing field is found
        """
        def build_exception(message: str) -> Exception:
            return Exception("Transaction Validation Failed -- {}\nfor transaction Dictionary: {}"
                             .format(message, tx))

        def check_fields(fields: tuple, d: dict):
            for field in fields:
                if field not in d:
                    raise build_exception("field {} missing".format(field))

        # Basic type checks
        if tx == None:
            raise TypeError('Transaction Validation Failed -- tx_dict is None')
        elif type(tx) is not dict:
            raise TypeError('Transaction Validation Failed -- tx_dict is of wrong type')

        # payload/metadata field checks
        if 'payload' not in tx:
            raise build_exception('payload field missing')
        elif 'metadata' not in tx:
            raise build_exception('metadata field is missing')

        payload = tx['payload']
        metadata = tx['metadata']

        # metadata checks
        if 'signature' not in metadata:
            raise build_exception('signature field missing from metadata')
        elif 'proof' not in metadata:
            raise build_exception('proof field missing from metadata')

        # payload checks
        if 'type' not in payload:
            raise build_exception('type field missing from payload')
        elif payload['type'] not in (TestNetTransaction.TX, TestNetTransaction.STAMP, TestNetTransaction.VOTE,
                                     TestNetTransaction.SWAP, TestNetTransaction.REDEEM):
            raise build_exception('invalid type {} in payload'.format(payload['type']))

        # Check required fields for each transaction type
        if payload['type'] == TestNetTransaction.TX:
            check_fields(('to', 'from', 'amount'), payload)
        elif payload['type'] == TestNetTransaction.STAMP:
            check_fields(('from', 'amount'), payload)
        elif payload['type'] == TestNetTransaction.VOTE:
            check_fields(('from', 'to'), payload)
        elif payload['type'] == TestNetTransaction.SWAP:
            check_fields(('from', 'to', 'amount', 'hash_lock', 'unix_expiration'), payload)
        elif payload['type'] == TestNetTransaction.REDEEM:
            check_fields(('redeem', 'redeem'), payload)

        return True

    @staticmethod
    def standard_tx(sender: str, to: str, amount: str):
        return TestNetTransaction.TX, sender, to, amount

    @staticmethod
    def stamp_tx(sender: str, amount):
        return TestNetTransaction.STAMP, sender, amount

    @staticmethod
    def vote_tx(sender: str, address):
        return TestNetTransaction.VOTE, sender, address

    @staticmethod
    def swap_tx(sender: str, recipient: str, amount: str, hash_lock: str, unix_expiration: str):
        return TestNetTransaction.SWAP, sender, recipient, amount, hash_lock, unix_expiration

    @staticmethod
    def redeem_tx(sender: str, secret: str):
        return TestNetTransaction.REDEEM, sender, secret

    @staticmethod
    def verify_tx(transaction, verifying_key, signature, wallet: Wallet, proof_system: POW):
        valid_signature = wallet.verify(verifying_key, str(transaction['payload']).encode(), signature)
        try:
            valid_proof = proof_system.check(str(transaction['payload']).encode(), transaction['metadata']['proof'][0])
        except:
            valid_proof = transaction['metadata']['proof'] == 's'
        return valid_signature, valid_proof

    @staticmethod
    def from_dict(tx_dict, use_stamp=False, wallet=ED25519Wallet, proof=POW):
        """
        Build a TestNetTransaction object from a dictionary.
        :param tx_dict: A dictionary containing the transaction data
        :param wallet: Wallet to use for transaction
        :param proof: Proof algorithm to use for transaction
        :return: A TestNetTransaction object
        """
        transaction = TestNetTransaction(wallet, proof)
        transaction.payload['metadata'] = tx_dict['metadata']
        payload = tx_dict['payload']

        tx_type = payload['type']

        if tx_type == TestNetTransaction.TX:
            sender, receiver, amount = payload['from'], payload['to'], str(payload['amount'])
            transaction.payload['payload'] = TestNetTransaction.standard_tx(sender, receiver, amount)
        elif tx_type == TestNetTransaction.STAMP:
            sender, amount = payload['from'], payload['amount']
            transaction.payload['payload'] = TestNetTransaction.stamp_tx(sender, amount)
        elif tx_type == TestNetTransaction.VOTE:
            sender, receiver = payload['from'], payload['to']
            transaction.payload['payload'] = TestNetTransaction.vote_tx(sender, receiver)
        elif tx_type == TestNetTransaction.SWAP:
            sender, receiver, amount, hash_lock, unix_expir = payload['from'], payload['to'], str(payload['amount']), \
                                                              payload['hash_lock'], payload['unix_expiration']
            transaction.payload['payload'] = TestNetTransaction.swap_tx(sender, receiver, amount, hash_lock, unix_expir)
        elif tx_type == TestNetTransaction.REDEEM:
            transaction.payload['payload'] = TestNetTransaction.redeem_tx(payload['to'], payload['secret'])
        else:
            raise Exception('Error building transaction from dict -- '
                            'Invalid type field in transaction dict: {}'.format(tx_dict))

        if use_stamp:
            transaction.payload['metadata']['proof'] = TestNetTransaction.STAMP
        else:
            transaction.payload['metadata']['proof'] = transaction.seal()

        return transaction

    def __init__(self, wallet, proof):
        super().__init__(wallet, proof)
        self.payload = {
                'payload' : None,
                'metadata' : {
                    'signature' : None,
                    'proof' : None
                }
            }

    def build(self, tx, s, use_stamp=False, complete=True):
        self.payload['payload'] = tx

        if complete:
            self.payload['metadata']['signature'] = self.sign(s)
            if use_stamp:
                self.payload['metadata']['proof'] = TestNetTransaction.STAMP
            else:
                self.payload['metadata']['proof'] = self.seal()

    def sign(self, s):
        return self.wallet.sign(s, str(self.payload['payload']).encode())

    def seal(self):
        return self.proof_system.find(str(self.payload['payload']).encode())
