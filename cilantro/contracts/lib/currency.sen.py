# do not delete the comment below. it is necessary for unit tests.
# UNITTEST_FLAG_CURRENCY_SENECA 1729

from seneca.libs.datatypes import hmap

# Declare Data Types
xrate = hmap('xrate', str, float)
balances = hmap('balances', str, int)
allowed = hmap('allowed', str, hmap(key_type=str, value_type=int))

# Initialization
xrate['TAU_STP'] = 1.0
balances['LamdenReserves'] = 0

@seed
def initialize_contract():
    # Deposit to all network founders
    ALL_WALLETS = [
        '324ee2e3544a8853a3c5a0ef0946b929aa488cbe7e7ee31a0fef9585ce398502',
        'a103715914a7aae8dd8fddba945ab63a169dfe6e37f79b4a58bcf85bfd681694',
        '20da05fdba92449732b3871cc542a058075446fedb41430ee882e99f9091cc4d',
        'ed19061921c593a9d16875ca660b57aa5e45c811c8cf7af0cfcbd23faa52cbcd',
        'cb9bfd4b57b243248796e9eb90bc4f0053d78f06ce68573e0fdca422f54bb0d2',
        'c1f845ad8967b93092d59e4ef56aef3eba49c33079119b9c856a5354e9ccdf84'
    ]
    SEED_AMOUNT = 1000000

    for w in ALL_WALLETS:
        balances[w] = SEED_AMOUNT

@export
def submit_stamps(stamps):
    assert stamps > 0, "Stamps supplied must be non-negative"
    if xrate['TAU_STP'] == 0:
        xrate['TAU_STP'] = 1.0
    amount = stamps * xrate['TAU_STP']
    balances[rt['origin']] -= amount
    balances['LamdenReserves'] += amount
    sender_balance = balances[rt['origin']]
    assert sender_balance >= 0, "Not enough funds to submit stamps"

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
    # print("minting {} to wallet {}".format(amount, to))
    assert rt['sender'] == rt['author'], 'Only the original contract author can mint!'

    balances[to] += amount
