class TransactionType:
    def __init__(self, _type, keys):
        keys.append('type')
        self.repr = dict([(k, None) for k in keys])
        self.repr['type'] = _type
        self.type = self.repr['type']
        print(self.repr)

    def is_transaction_type(self, tx):
        return tx.keys() == self.repr.keys() and tx['type'] == self.repr['type']
