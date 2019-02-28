from cilantro_ee.utils.lazy_property import *


class Thing:

    def __init__(self, v):
        self.v = v
        set_lazy_property(self, 'do_that', self.v)

    @lazy_func
    def do_that(self):
        print("donig that!")
        return self.v


if __name__ == '__main__':
    t = Thing('hiiii')
    print("1")
    print(t.do_that())
    print("2")
    print(t.do_that())
    print("3")
    print(t.do_that())
