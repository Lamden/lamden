from cilantro.transactions import Transaction

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
    def standard_tx(to: str, amount: str):
        return TestNetTransaction.TX, to, amount

    @staticmethod
    def stamp_tx(amount):
        return TestNetTransaction.STAMP, amount

    @staticmethod
    def vote_tx(address):
        return TestNetTransaction.VOTE, address

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

    def verify_tx(self, tx: dict, v, sig: bytes):
        # perhaps should strong type this to a named tuple for better type assertion
        return self.wallet.verify(v, str(tx).encode, sig)
