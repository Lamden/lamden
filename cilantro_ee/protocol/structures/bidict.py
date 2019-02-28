class Bidict(dict):
    def __setitem__(self, key, value):
        super(Bidict, self).__setitem__(value, key)
        super(Bidict, self).__setitem__(key, value)

    def __delitem__(self, key):
        val = self[key]
        super(Bidict, self).__delitem__(val)
        super(Bidict, self).__delitem__(key)
