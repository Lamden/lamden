import election_house

ELECTION_WINDOW = datetime.WEEKS * 1

version_state = Hash()
has_voted = Hash(default_value=False)
vote_state = Hash()
startup = Hash()

@export
def start_vote(lamden_tag: str, contracting_tag: str):
    assert ctx.caller in election_house.current_value_for_policy('masternodes'), 'Not a member!'

    if voting_expired():
        vote_state.clear()
        has_voted.clear()

    assert vote_state['started'] is None, 'Another voting in progress!'

    vote_state['lamden_tag'] = lamden_tag
    vote_state['contracting_tag'] = contracting_tag
    vote_state['votes'] = 1
    vote_state['started'] = now
    has_voted[ctx.caller] = True

@export
def vote():
    assert ctx.caller in election_house.current_value_for_policy('masternodes'), 'Invalid voter!'
    assert vote_state['started'] is not None, 'No voting in progress!'

    if voting_expired():
        vote_state.clear()
        has_voted.clear()
    else:
        if has_consensus():
            version_state['lamden_tag'] = vote_state['lamden_tag']
            version_state['contracting_tag'] = vote_state['contracting_tag']
            vote_state.clear()
            has_voted.clear()
        else:
            assert not has_voted[ctx.caller], 'Cannot vote twice!'
            vote_state['votes'] += 1
            has_voted[ctx.caller] = True
@export
def startup(lamden_tag: str, contracting_tag: str):
    assert ctx.caller in election_house.current_value_for_policy('masternodes'), 'Not a member!'

    startup[ctx.caller, 'lamden_tag'] = lamden_tag
    startup[ctx.caller, 'contracting_tag'] = contracting_tag

def has_consensus():
    return vote_state['votes'] >= (len(election_house.current_value_for_policy('masternodes')) * 2 // 3 + 1)

def voting_expired():
    return vote_state['started'] is not None and now - vote_state['started'] > ELECTION_WINDOW