from cilantro.transactions import Transaction
from cilantro.wallets import Wallet
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
    def verify_tx(tx, v, sig, wallet: Wallet, proof_system: POW):
        valid_signature = wallet.verify(v, str(tx['payload']).encode(), sig)
        try:
            valid_proof = proof_system.check(str(tx['payload']).encode(), tx['metadata']['proof'][0])
        except:
            valid_proof = tx['metadata']['proof'] == 's'
        return valid_signature, valid_proof

    def __init__(self, wallet, proof):
        super().__init__(wallet, proof)
        self.payload = TestNetTransaction.payload_format

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
