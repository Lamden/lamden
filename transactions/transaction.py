def new(payload, signature, proof):
    raise NotImplementedError

def payload(*args):
    raise NotImplementedError

def metadata(payload, s):
    raise NotImplementedError

def build(**kwargs):
    raise NotImplementedError

def find_nonce(o):
    raise NotImplementedError

def check_proof(o, proof):
    raise NotImplementedError

class TransactionType(object):
    def __init__(self, wallet):
        self.wallet = wallet

    def new(payload, signature, proof):
        raise NotImplementedError

    def payload(*args):
        raise NotImplementedError

    def metadata(payload, s):
        raise NotImplementedError

    def build(**kwargs):
        raise NotImplementedError

    def find_nonce(o):
        raise NotImplementedError

    def check_proof(o, proof):
        raise NotImplementedError