

class Base:
    _ATTR = {}

class Sub1(Base): pass
class Sub2(Base): pass
class Sub3(Base): pass

# s1, s2, s3 = Sub1(), Sub2(), Sub3()

Sub1._ATTR['this-was-set'] = 'by sub 1'
Sub2._ATTR['and-this-by'] = 'by sub 2'

print(Sub1._ATTR)
print(Sub2._ATTR)
print(Sub3._ATTR)
