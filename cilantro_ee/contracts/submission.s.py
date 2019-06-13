def submit_contract(name, code, constructor_args={}):
    author = ctx.signer
    __Contract().submit(name=name, code=code, author=author, constructor_args=constructor_args)
