import json
import os

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

dynamic_imports = [
    ['cilantro.protocol.proofs', Constants.Protocol.Proofs],
    ['cilantro.protocol.wallets', Constants.Protocol.Wallets],
    ['cilantro.protocol.serialization', Constants.Protocol.Serialization],
]

for d_i in dynamic_imports:
    c = __import__(d_i[0], fromlist=[d_i[1]])
    d_i[1] = getattr(c, d_i[1])