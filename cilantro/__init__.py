import json
import os
from decimal import getcontext

def snake_to_pascal(s):
    s = s.split('-')
    new_str = ''
    for ss in s:
        new_str += ss.title()
    return new_str


path = os.path.join(os.path.dirname(__file__), 'config.json')
config = json.load(open(path))


class Constants:
    classes = []
    json = None

    @classmethod
    def new_class(cls, name, **kwargs):
        c = type(name, (cls,), kwargs)
        globals()[name] = c
        return c

    @classmethod
    def add_attr(cls, name, value):
        setattr(cls, name, value)

    @classmethod
    def build_from_json(cls, d):
        for k in d.keys():
            if type(d[k]) == dict:
                new_class = cls.new_class(name=snake_to_pascal(k))
                cls.add_attr(name=snake_to_pascal(k), value=new_class)
                cls.classes.append(new_class)
                cls.build_from_json(d[k])
            else:
                last_class = cls.classes[-1]
                setattr(last_class, snake_to_pascal(k), d[k])

    @classmethod
    def __str__(cls):
        return str(cls.json)


Constants.build_from_json(config)
Constants.json = config

c = __import__('cilantro.protocol.proofs', fromlist=[Constants.Protocol.Proofs])
Constants.Protocol.Proofs = getattr(c, Constants.Protocol.Proofs)

c = __import__('cilantro.protocol.wallets', fromlist=[Constants.Protocol.Wallets])
Constants.Protocol.Wallets = getattr(c, Constants.Protocol.Wallets)

c = __import__('cilantro.protocol.interpreters', fromlist=[Constants.Protocol.Interpreters])
Constants.Protocol.Interpreters = getattr(c, Constants.Protocol.Interpreters)

# Config fixed point decimals
getcontext().prec = Constants.Protocol.SignificantDigits