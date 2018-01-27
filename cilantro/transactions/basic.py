from cilantro.transactions import Transaction

class BasicTransaction(Transaction):
    def __init__(self, wallet, proof):
        super().__init__(wallet, proof)
        self.payload = {
            'payload' : {
                'to' : None,
                'amount' : None,
                'from' : None
            },
            'metadata' : {
                'sig' : None,
                'proof' : None
            }
        }

    def build(self, to, amount, s, v, complete=True):
        self.payload['payload']['to'] = to
        self.payload['payload']['amount'] = amount
        self.payload['payload']['from'] = v

        if complete:
            self.payload['metadata']['sig'] = self.sign(self.payload['payload'])
            self.payload['metadata']['proof'] = self.seal(self.payload['payload'])

    def sign(self, payload):
        return self.wallet.sign(payload)

    def seal(self, payload):
        return self.proof_system.find(payload)
