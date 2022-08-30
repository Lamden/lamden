import election_house


ELECTION_WINDOW = datetime.WEEKS * 1

upgrade_state = Hash()                  # Main storage
has_voted = Hash(default_value=False)   # Address -> Votes hash


@construct
def seed():
    upgrade_state['locked'] = False
    upgrade_state['consensus'] = False

    upgrade_state['votes'] = 0
    upgrade_state['voters'] = 0


def start_vote(lamden_branch_name: str, contracting_branch_name: str, pepper: str):
    upgrade_state['locked'] = True
    upgrade_state['pepper'] = pepper
    upgrade_state['lamden_branch_name'] = lamden_branch_name
    upgrade_state['contracting_branch_name'] = contracting_branch_name

    upgrade_state['votes'] = 0

    upgrade_state['voters'] = len(election_house.current_value_for_policy('masternodes'))

    upgrade_state['started'] = now


def is_valid_voter(address: str):
    if address in election_house.current_value_for_policy('masternodes'):
        return True

    return False


@export
def vote(**kwargs):
    assert not has_voted[ctx.caller], 'Cannot vote twice!'
    assert is_valid_voter(ctx.caller), 'Invalid voter!'
    assert not upgrade_state['consensus'], 'Consensus already achieved!'

    if upgrade_state['started'] is not None and now - upgrade_state['started'] > ELECTION_WINDOW:
        upgrade_state.clear()
        has_voted.clear()

    if not upgrade_state['locked']:
        start_vote(**kwargs)
        upgrade_state['votes'] += 1
        has_voted[ctx.caller] = True

    elif upgrade_state['votes'] + 1 >= (upgrade_state['voters'] * 2 // 3):
        upgrade_state['consensus'] = True
        has_voted.clear()

    else:
        upgrade_state['votes'] += 1
        has_voted[ctx.caller] = True
