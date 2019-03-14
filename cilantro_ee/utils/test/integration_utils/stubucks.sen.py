from seneca.libs.storage.datatypes import Hash

balances = Hash('balances', default_value=0)
custodials = Hash('custodials', default_value=0)


@seed
def seed():
    balances['324ee2e3544a8853a3c5a0ef0946b929aa488cbe7e7ee31a0fef9585ce398502'] = 1000000

@export
def transfer(to, amount):
    assert balances[rt['sender']] >= amount
    balances[to] += amount
    balances[rt['sender']] -= amount

@export
def add_to_custodial(to, amount):
    assert balances[rt['sender']] >= amount
    custodials[rt['sender']][to] += amount
    balances[rt['sender']] -= amount

@export
def remove_from_custodial(to, amount):
    assert custodials[rt['sender']][to] >= amount
    balances[rt['sender']] += amount
    custodials[rt['sender']][to] -= amount

@export
def spend_custodial(_from, amount, to):
    assert custodials[_from][rt['sender']] >= amount
    balances[to] += amount
    custodials[_from][rt['sender']] -= amount
