import currency

owner = Variable()

@construct
def seed(vk):
    owner.set(vk)

@export
def withdraw(amount):
    assert ctx.caller == owner.get(), 'Not owner!'
    currency.transfer(amount, ctx.caller)

@export
def change_owner(vk):
    assert ctx.caller == owner.get(), 'Not owner!'
    owner.set(vk)
