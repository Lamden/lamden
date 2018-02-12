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
    def redeem_tx(secret: str):
        return TestNetTransaction.REDEEM, secret

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

        sender = payload['from']
        receiver = payload['to']
        amount = str(payload['amount'])
        tx_type = payload['type']

        if tx_type == TestNetTransaction.TX:
            transaction.payload['payload'] = TestNetTransaction.standard_tx(sender, receiver, amount)
        elif tx_type == TestNetTransaction.STAMP:
            transaction.payload['payload'] = TestNetTransaction.stamp_tx(sender, amount)
        elif tx_type == TestNetTransaction.VOTE:
            transaction.payload['payload'] = TestNetTransaction.vote_tx(sender, receiver)
        elif tx_type == TestNetTransaction.SWAP:
            # TODO -- implement this
            raise NotImplementedError
        elif tx_type == TestNetTransaction.REDEEM:
            # TODO -- implement this
            raise NotImplementedError
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
