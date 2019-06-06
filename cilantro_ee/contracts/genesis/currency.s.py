supply = Variable()
balances = Hash(default_value=0)

@construct
def seed():
    #balances[ctx.caller] = 288_090_567

    seed_amount = 1000000
    supply.set(0)

    founder_wallets = [
        "8143f569f258c33de00d71a6527eadd5e22a88b0f16bee3f13230d26dd8a5e46",
        "6fa435ea82e54d55b20599609b750f2602c596edbd70520c156a7d907e26926b",
        "9dcef7bceb11e0d7f4ce687d343be819fb96c4abc3bb87fe4126849230c93a2a",
        "64cdc0774705e09d1f2c3288766721ad1fa4a9cfd2be8260c127c0ea3475dd8e",
        "772de9fcb7a44d4d91c6419f9f79cdd81b9ba874400b57365b288fac20d28b2c",
        "1f2995f6cb7afad770efdf4615be264fae145d796fc7fb3b9794372812e361cd",
        "2b060b761c8e698168cc9641ef2b22ff357464cb324866631572508defcc0898",
        "ed3722a66e806935c58f830813a9eb69f1beadff704ad1e611b741d0c7fb6190",
        "b8491def67aa7f7bf03d1d2642e029ef82f6c73e8478e78ebe536e3c2b011aec",
        "76bebe49e768818773bda994491dc271f8e360917a820278d4e52d7a7f76c9af",
        "d0907067177ad93e6cb27df90e2c0c48d9f881ce5b4a00d51c09ef5dbe4d90a6",
        "41250f9159790f9c9b9e5cd558b2e42a86836b538dd091f2c747998fc90fa257",
        "e5c2815253b301f50a4e63ce7c5c61db9c65f543333e15257c34cf5c9f0b46e5",
        "8e16d6c9054cc90b4f7443ae3ceeee3fd64db22eb46f2421c51bc5f203ecbb15",
        "1f328c2ff4ccdfe1b66724304cc88be3b00fd08d85851a086440d4faf0858888",
        "93aeefec5d87bc890b02fec280ab9c79803d2ab71d1cb274d7090e9b84cd6f8a",
        "3c820d80eadfef392ab97ceb9c0d3459f45d14be5cbcb680f84910d7778483ae",
        "aacfe4211a363363211f300a9bfcd70072d2615ccf58cd7fdb53c2a8d74d1c7e",
        "dcbcb40c83e865f805e30842b810c330031645edc405ebe6376fda84da2d82b6",
        "ec6361c4849faad114748b00a801076b0ddbeda78164c51079ab0abab5f2b6bd",
        "7cc186a08d7a2f510d2670af4787b73b40d91abd8d1817125f0de850f2e9bd96",
        "5d7f99022d87d344150b598e79477a580ae1ccd8d681ba46330597dbbdfd91bc",
        "db3ea9f7b716896bae3efa78da381e81fc6707c1a2387ffd3e97e62b00b2bc69",
        "f022edef56754196edfb591ea9f5878164fd9ce26e5c4fc2ee9260717cd751a7",
        "5568d257e567c043e7fbf8d6425256a174da2719f6829bbe46a4c2bbfc8bb9a4",
        "1bf8eae89e98dcd8066207a667c30a4d6345886c148eba359f0a95fe701f754d",
    ]

    for w in founder_wallets:
        # print('Minting {} with {} coins'.format(w, seed_amount))
        balances[w] = seed_amount

        s = supply.get()
        s += seed_amount
        supply.set(s)
    # print('Done minting!')

@export
def transfer(amount, to):
    sender = ctx.caller

    balance = balances[sender]

    assert balance >= amount, 'Current balance {} from sender {} is less than amount {}.'.format(
        balance,
        sender,
        amount
    )

    balances[sender] -= amount
    balances[to] += amount

    # print('Succesfully sent {} coins to {}. {} updated from {} to {}'.format(
        # amount,
        # to,
        # sender,
        # balance,
        # balances[sender]
    # ))

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
