# Convenience
I = importlib

# Main state datum
contract_to_policy = Hash()
policy_to_contract = Hash()

# Policy interface
policy_interface = [
    I.Func('vote', args=('vk', 'obj')),
    I.Func('current_value')
]


@export
def register_policy(policy, contract):
    if policy_to_contract[policy] is None and contract_to_policy[contract] is None:
        # Attempt to import the contract to make sure it is already submitted
        p = I.import_module(contract)

        # Assert ownership is election_house and interface is correct
        assert I.owner_of(p) == ctx.this, \
            'Election house must control the policy contract!'

        assert I.enforce_interface(p, policy_interface), \
            'Policy contract does not follow the correct interface'


        policy_to_contract[policy] = contract
        contract_to_policy[contract] = policy
    else:
        raise Exception('Policy already registered')


@export
def current_value_for_policy(policy: str):
    contract = policy_to_contract[policy]
    assert contract is not None, 'Invalid policy.'

    p = I.import_module(contract)

    return p.current_value()


@export
def vote(policy, value):
    # Verify policy has been registered
    contract_name = policy_to_contract[policy]
    assert contract_name is not None, 'Invalid policy.'

    p = I.import_module(contract_name)

    p.vote(vk=ctx.caller, obj=value)
