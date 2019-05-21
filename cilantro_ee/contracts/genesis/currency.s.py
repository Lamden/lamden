supply = Variable()
balances = Hash(default_value=0)

@construct
def seed():
    #balances[ctx.caller] = 288_090_567

    seed_amount = 1000000

    founder_wallets = [
        '324ee2e3544a8853a3c5a0ef0946b929aa488cbe7e7ee31a0fef9585ce398502',
        'a103715914a7aae8dd8fddba945ab63a169dfe6e37f79b4a58bcf85bfd681694',
        '20da05fdba92449732b3871cc542a058075446fedb41430ee882e99f9091cc4d',
        'ed19061921c593a9d16875ca660b57aa5e45c811c8cf7af0cfcbd23faa52cbcd',
        'cb9bfd4b57b243248796e9eb90bc4f0053d78f06ce68573e0fdca422f54bb0d2',
        'c1f845ad8967b93092d59e4ef56aef3eba49c33079119b9c856a5354e9ccdf84'
    ]

    for w in founder_wallets:
        balances[w] = seed_amount

    supply.set(balances[ctx.caller])

@export
def transfer(amount, to):
    sender = ctx.caller
    assert balances[sender] >= amount, 'Not enough coins to send!'

    balances[sender] -= amount
    balances[to] += amount

@export
def balance_of(account):
    return balances[account]

@export
def total_supply():
    return supply.get()

@export
def allowance(owner, spender):
    return balances[owner, spender]

@export
def approve(amount, to):
    sender = ctx.caller
    balances[sender, to] += amount
    return balances[sender, to]

@export
def transfer_from(amount, to, main_account):
    sender = ctx.caller

    assert balances[main_account, sender] >= amount, 'Not enough coins approved to send! You have {} and are trying to spend {}'\
        .format(balances[main_account, sender], amount)
    assert balances[main_account] >= amount, 'Not enough coins to send!'

    balances[main_account, sender] -= amount
    balances[main_account] -= amount

    balances[to] += amount