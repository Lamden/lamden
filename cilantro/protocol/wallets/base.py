class Wallet(object):

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
