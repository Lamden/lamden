@__export('submission')
def submit_contract(name: str, code: str, owner: Any=None, constructor_args: dict={}):
    assert not name.isdigit() and all(c.isalnum() or c == '_' for c in name), 'Invalid contract name!'
    __Contract().submit(name=name, code=code, owner=owner, constructor_args=constructor_args)
