import election_house

ELECTION_WINDOW = datetime.WEEKS * 1

S = Hash()
vote_state = Hash()

@construct
def seed(lamden_tag: str, contracting_tag: str):
    S['lamden_tag'] = lamden_tag
    S['contracting_tag'] = contracting_tag

@export
def propose_upgrade(lamden_tag: str, contracting_tag: str):
    assert ctx.caller in election_house.current_value_for_policy('masternodes'), 'Not a member!'
    assert lamden_tag is not None and lamden_tag != '' and contracting_tag is not None and contracting_tag != '', 'Version string is not valid!'

    if expired():
        vote_state.clear()

    assert vote_state['started'] is None, 'Another voting in progress!'

    vote_state['lamden_tag'] = lamden_tag
    vote_state['contracting_tag'] = contracting_tag
    vote_state['yays'] = 1
    vote_state['nays'] = 0
    vote_state['started'] = now
    vote_state['positions', ctx.caller] = True

@export
def vote(position: bool):
    assert ctx.caller in election_house.current_value_for_policy('masternodes'), 'Invalid voter!'
    assert vote_state['started'] is not None, 'No open proposals!'
    assert isinstance(position, bool), 'Position is not valid!'

    if expired():
        vote_state.clear()
    else:
        assert vote_state['positions', ctx.caller] is None, 'Cannot vote twice!'
        if position:
            vote_state['yays'] += 1
        else:
            vote_state['nays'] += 1
        vote_state['positions', ctx.caller] = True

        check_consensus()

@export
def startup(lamden_tag: str, contracting_tag: str):
    assert ctx.caller in election_house.current_value_for_policy('masternodes'), 'Not a member!'
    assert lamden_tag is not None and lamden_tag != '' and contracting_tag is not None and contracting_tag != '', 'Tags are not valid!'

    S[ctx.caller, 'lamden_tag'] = lamden_tag
    S[ctx.caller, 'contracting_tag'] = contracting_tag

def get_majority():
    return len(election_house.current_value_for_policy('masternodes')) * 2 // 3 + 1

def check_consensus():
    majority = get_majority()
    if vote_state['yays'] >= majority:
        S['lamden_tag'] = vote_state['lamden_tag']
        S['contracting_tag'] = vote_state['contracting_tag']
        vote_state.clear()
    elif vote_state['nays'] >= majority or vote_state['yays'] + vote_state['nays'] == len(election_house.current_value_for_policy('masternodes')):
        vote_state.clear()

def expired():
    return vote_state['started'] is not None and now - vote_state['started'] > ELECTION_WINDOW