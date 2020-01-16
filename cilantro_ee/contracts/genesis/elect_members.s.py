import currency
import election_house

S = Hash()
Q = Variable()
STAMP_COST = 20_000

policy_name = Variable()
member_cost = Variable()

@construct
def seed(policy='masternodes', cost=100_000):
    # Set as empty list
    Q.set({})
    policy_name.set(policy)
    member_cost.set(cost)

@export
def register():
    # Make sure someone is already staked
    assert not S['registered', ctx.signer], 'Already registered.'

    currency.transfer_from(member_cost.get(), ctx.caller, ctx.this)

    S['registered', ctx.signer] = True

    q_ = Q.get()
    q_[ctx.signer] = 0
    Q.set(q_)

@export
def unregister():
    mns = election_house.get_policy(policy_name.get())
    assert ctx.caller not in mns, "Can't unstake if in governance."
    currency.transfer(member_cost.get(), ctx.caller)

@export
def vote(address):
    assert S['registered', address]

    # Determine if caller can vote
    v = S['last_voted', ctx.signer]
    assert now - v > DAYS * 1 or v is None, 'Voting again too soon.'

    # Deduct small vote fee
    vote_cost = STAMP_COST / election_house.get_policy('stamp_cost')
    currency.transfer_from(vote_cost, ctx.signer, 'blackhole')

    # Update last voted variable
    S['last_voted', ctx.signer] = now

    # Update vote dict
    q_ = Q.get()
    q_[address] += 1
    Q.set(q_)

@export
def top_masternode():
    q_ = Q.get()

    if len(q_) == 0:
        return None

    top = sorted(q_.items(), key=lambda x: x[1], reverse=True)

    return top[0][0]

@export
def pop_top():
    assert ctx.caller == policy_name.get(), 'Wrong smart contract caller.'

    top = top_masternode()

    q_ = Q.get()
    del q_[top]
    Q.set(q_)
