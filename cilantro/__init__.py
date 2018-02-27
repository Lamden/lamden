import json


def snake_to_pascal(s):
    s = s.split('-')
    new_str = ''
    for ss in s:
        new_str += ss.title()
    return new_str


config = json.load(open('./config.json'))


class Constants:
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
                new_class = cls.new_class(name=k)
                cls.add_attr(name=k, value=new_class)
                classes.append(new_class)
                cls.build_from_json(d[k])
            else:
                last_class = classes[-1]
                setattr(last_class, k, d[k])


classes = []

Constants.build_from_json(config)

print(Constants.protocol.wallet)