class Wallet(object):
    def __init__(self, s=None):
        if s == None:
            self.s, self.v = Wallet.new()
        else:
            self.s, self.v = Wallet.format_to_keys(s)
            self.s, self.v = Wallet.keys_to_format(self.s, self.v)

    @classmethod
    def generate_keys(cls):
        raise NotImplementedError

    @classmethod
    def keys_to_format(cls, s, v):
        raise NotImplementedError

    @classmethod
    def format_to_keys(cls, s):
        raise NotImplementedError

    @classmethod
    def new(cls):
        raise NotImplementedError

    @classmethod
    def sign(cls, s, msg):
        raise NotImplementedError

    @classmethod
    def verify(cls, v, msg, sig):
        raise NotImplementedError