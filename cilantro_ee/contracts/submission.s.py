@__export('submission')
def submit_contract(name, code, owner=None, constructor_args={}):
    __Contract().submit(name=name, code=code, owner=owner, constructor_args=constructor_args)
