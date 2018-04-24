class Test:
    def __init__(self, name):
        self._name = name

    @lazy_property
    def silly_name(self):
        print("computing property!")
        return "SILLYLOL -- " + self._name




print("starting test")
t = Test('billy')