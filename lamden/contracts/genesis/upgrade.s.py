import election_house

ELECTION_WINDOW = datetime.WEEKS * 1

version_state = Hash()
has_voted = Hash(default_value=False)
vote_state = Hash()
startup = Hash()

@export
def propose_upgrade(lamden_tag: str, contracting_tag: str):
    assert ctx.caller in election_house.current_value_for_policy('masternodes'), 'Not a member!'
    assert lamden_tag is not None and lamden_tag != '' and contracting_tag is not None and contracting_tag != '', 'Version string is not valid!'

    if expired():
        vote_state.clear()
        has_voted.clear()

    assert vote_state['started'] is None, 'Another voting in progress!'

    vote_state['lamden_tag'] = lamden_tag
    vote_state['contracting_tag'] = contracting_tag
    vote_state['yays'] = 1
    vote_state['nays'] = 0
    vote_state['started'] = now
    has_voted[ctx.caller] = True

@export
def vote(position):
    assert ctx.caller in election_house.current_value_for_policy('masternodes'), 'Invalid voter!'
    assert vote_state['started'] is not None, 'No open proposals!'
    assert type(position) == bool, 'Position is not valid!'

    if expired():
        vote_state.clear()
        has_voted.clear()
    else:
        assert not has_voted[ctx.caller], 'Cannot vote twice!'
        if position:
            vote_state['yays'] += 1
        else:
            vote_state['nays'] += 1
        has_voted[ctx.caller] = True

        check_consensus()

@export
def startup(lamden_tag: str, contracting_tag: str):
    assert ctx.caller in election_house.current_value_for_policy('masternodes'), 'Not a member!'
    assert lamden_tag is not None and lamden_tag != '' and contracting_tag is not None and contracting_tag != '', 'Tags are not valid!'

    startup[ctx.caller, 'lamden_tag'] = lamden_tag
    startup[ctx.caller, 'contracting_tag'] = contracting_tag

def get_majority():
    return len(election_house.current_value_for_policy('masternodes')) * 2 // 3 + 1

def check_consensus():
    majority = get_majority()
    if vote_state['yays'] >= majority:
        version_state['lamden_tag'] = vote_state['lamden_tag']
        version_state['contracting_tag'] = vote_state['contracting_tag']
        vote_state.clear()
        has_voted.clear()
    elif vote_state['nays'] >= majority:
        vote_state.clear()
        has_voted.clear()

def expired():
    return vote_state['started'] is not None and now - vote_state['started'] > ELECTION_WINDOW