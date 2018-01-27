from cilantro.transactions import Transaction

TX = 't'
STAMP = 's'
VOTE = 'v'


def standard_tx(to, sender, amount):
    return TX, to, sender, amount


def stamp_tx(amount):
    return STAMP, amount


def vote_tx(address):
    return VOTE, address


class TestNetTransaction(Transaction):
    # support stamp transactions, vote transactions, etc.
    def __init__(self, wallet, proof):
        super().__init__(wallet, proof)
        self.payload = {
            'payload': None,
            'metadata': {
                'sig': None,
                'proof': None
            }
        }

    def build(self, tx, use_stamp=False, complete=True):

        self.payload['payload'] = tx

        if complete:
            self.payload['metadata']['sig'] = self.sign(self.payload['payload'])
            if use_stamp:
                self.payload['metadata']['proof'] = STAMP
            else:
                self.payload['metadata']['proof'] = self.seal(self.payload['payload'])

    def sign(self, payload):
        return self.wallet.sign(payload)

    def seal(self, payload):
        return self.proof_system.find(payload)
