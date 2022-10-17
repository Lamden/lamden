import currency
import election_house

S = Hash()

@construct
def seed(election_period_length=datetime.DAYS * 1):
    S['election_period_length'] = election_period_length
    reset()

@export
def current_value():
    return S

@export
def vote(voter_vk: str, obj: list):
    assert voter_vk in election_house.current_value_for_policy('masternodes'), 'Not a member.'
    assert type(obj) == list, 'Pass a list!'

    if S['motion_start'] is None:
        recipient_vk, amount = obj
        assert_recipient_vk_and_amount_is_valid(recipient_vk, amount)

        S['recipient_vk'] = recipient_vk
        S['amount'] = amount
        S['motion_start'] = now
    else:
        if now - S['motion_start'] >= S['election_period_length']:
            reset()
            return

        position, = obj
        assert_vote_is_valid(voter_vk, position)

        S['positions', voter_vk] = position
        if position is True:
            S['yays'] += 1
        else:
            S['nays'] += 1

        total_members = len(election_house.current_value_for_policy('masternodes'))
        if len(S['positions'].all()) >= (total_members * 3 // 5) + 1:
            if S['yays'] >= (total_members * 7 // 10) + 1:
                pass_motion()
            elif S['nays'] >= (total_members * 7 // 10) + 1:
                reset()

def pass_motion():
    currency.transfer(S['amount'], S['recipient_vk'])
    reset()

def reset():
    S['yays'] = 0
    S['nays'] = 0
    S['motion_start'] = None
    S['recipient_vk'] = None
    S['amount'] = None
    S.clear('positions')

def assert_recipient_vk_and_amount_is_valid(vk: str, amount: int):
    assert vk is not None, 'No recipient VK provided.'
    assert type(vk) == str, 'Recipient VK is not a string.'
    assert len(vk) == 64, 'Recipient VK is not 64 characters.'
    int(vk, 16)

    assert amount is not None, 'No amount provided.'
    assert type(amount) == int, 'Amount is not an integer.'
    assert amount > 0, 'Amount is not greater than zero.'

def assert_vote_is_valid(voter_vk: str, position: bool):
    assert S['positions', voter_vk] is None, 'VK already voted.'
    assert type(position) == bool, 'Invalid position.'