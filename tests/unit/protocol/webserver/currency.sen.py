from seneca.libs.datatypes import hmap

balances = hmap('balances', str, int)
allowed = hmap('allowed', str, hmap(value_type=int))
market = hmap('market', str, int)

@seed
def deposit_to_all_wallets():
    market['stamps_to_tau'] = 1
    balances['lorde'] = 10000
    balances['john'] = 10000
    balances['peter'] = 10000
    balances['griffin'] = 10000

@export
def submit_stamps(stamps):
    amount = stamps / market['stamps_to_tau']
    transfer('black_hole', int(amount))

@export
def balance_of(wallet_id):
    return balances[wallet_id]

@export
def transfer(to, amount):
    # print("transfering from {} to {} with amount {}".format(rt['sender'], to, amount))
    balances[rt['sender']] -= amount
    balances[to] += amount
    sender_balance = balances[rt['sender']]

    assert sender_balance >= 0, "Sender balance must be non-negative!!!"

@export
def approve(spender, amount):
    allowed[rt['sender']][spender] = amount


@export
def transfer_from(_from, to, amount):
    assert allowed[_from][rt['sender']] >= amount
    assert balances[_from] >= amount

    allowed[_from][rt['sender']] -= amount
    balances[_from] -= amount
    balances[to] += amount


@export
def allowance(approver, spender):
    return allowed[approver][spender]


@export
def mint(to, amount):
    assert rt['sender'] == rt['author'], 'Only the original contract author can mint!'

    balances[to] += amount
