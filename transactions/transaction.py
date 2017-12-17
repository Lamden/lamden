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

def new(payload, signature, proof):
    return 0