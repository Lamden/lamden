def submit_contract(name, code):
    author = ctx.signer
    __Contract().submit(name=name, code=code, author=author)