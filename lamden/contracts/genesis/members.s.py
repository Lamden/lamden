import hash_lists

# Actions
INTRODUCE_MOTION = 'introduce_motion'
VOTE_ON_MOTION = 'vote_on_motion'

# Motions
NO_MOTION = 0
REMOVE_MEMBER = 1
ADD_SEAT = 2
REMOVE_SEAT = 3

VOTING_PERIOD = datetime.DAYS * 1

S = Hash()
minimum_nodes = Variable()
candidate_contract = Variable()

@construct
def seed(initial_members: list, minimum: int=1, candidate: str='elect_members'):
    hash_lists.store_list(list_name="members", list_data=initial_members)

    minimum_nodes.set(minimum)
    candidate_contract.set(candidate)

    S['yays'] = 0
    S['nays'] = 0

    S['current_motion'] = NO_MOTION
    S['motion_opened'] = now

@export
def quorum_max():
    return (int(get_members_length()) * 2 / 3) + 1

@export
def quorum_min():
    return min(quorum_max(), minimum_nodes.get())

@export
def current_value():
    return get_members()

@export
def vote(vk: str, obj: list):
    assert type(obj) == list, 'Pass a list!'

    arg = None

    if len(obj) == 3:
        action, position, arg = obj
    else:
        action, position = obj

    assert_vote_is_valid(vk, action, position, arg)

    if action == INTRODUCE_MOTION:
        introduce_motion(position, arg)

    else:
        assert S['current_motion'] != NO_MOTION, 'No motion proposed.'

        if now - S['motion_opened'] >= VOTING_PERIOD:
            reset()

        assert S['positions', vk] is None, 'VK already voted.'

        if position is True:
            S['yays'] += 1
            S['positions', vk] = position
        else:
            S['nays'] += 1
            S['positions', vk] = position

        members_length = get_members_length()

        if S['yays'] >= members_length // 2 + 1:
            pass_current_motion()
            reset()

        elif S['nays'] >= members_length // 2 + 1:
            reset()


def assert_vote_is_valid(vk: str, action: str, position: bool, arg: Any=None):
    assert member_in_list(vk), 'Not a member.'

    assert action in [INTRODUCE_MOTION, VOTE_ON_MOTION], 'Invalid action.'

    if action == INTRODUCE_MOTION:
        assert S['current_motion'] == NO_MOTION, 'Already in motion.'
        assert 0 < position <= REMOVE_SEAT, 'Invalid motion.'
        if position == REMOVE_MEMBER:
            assert_vk_is_valid(arg)

    elif action == VOTE_ON_MOTION:
        assert type(position) == bool, 'Invalid position'


def assert_vk_is_valid(vk: str):
    assert vk is not None, 'No VK provided.'
    assert type(vk) == str, 'VK not a string.'
    assert len(vk) == 64, 'VK is not 64 characters.'
    # assert vk == ctx.signer, 'Signer has to be the one voting to remove themselves.'
    int(vk, 16)


def introduce_motion(position: int, arg: Any):
    # If remove member, must be a member that already exists
    assert position <= REMOVE_SEAT, 'Invalid position.'
    if position == REMOVE_MEMBER:
        assert member_in_list(arg), 'Member does not exist.'
        assert get_members_length() > minimum_nodes.get(), 'Cannot drop below current quorum.'
        S['member_in_question'] = arg

    S['current_motion'] = position
    S['motion_opened'] = now


def pass_current_motion():
    current_motion = S['current_motion']

    if current_motion == REMOVE_MEMBER:
        hash_lists.remove_by_value(
            list_name="members",
            value=S['member_in_question'],
            remove_all=True
        )
    elif current_motion == ADD_SEAT:
        # Get the top member
        member_candidates = importlib.import_module(candidate_contract.get())
        new_mem = member_candidates.top_member()

        # Append it to the list, and remove it from pending
        if new_mem is not None:
            hash_lists.add_to_list(
                list_name="members",
                value=new_mem
            )
            member_candidates.pop_top()

    elif current_motion == REMOVE_SEAT:
        # Get least popular member
        member_candidates = importlib.import_module(candidate_contract.get())
        old_mem = member_candidates.last_member()

        # Remove them from the list and pop them from deprecating
        if old_mem is not None:
            hash_lists.remove_by_value(
                list_name="members",
                value=old_mem,
                remove_all=True
            )
            member_candidates.pop_last()

def get_members():
    return hash_lists.get_list(list_name="members")

def get_members_length():
    return hash_lists.list_length(list_name="members")

def member_in_list(vk: str):
    return hash_lists.is_in_list(list_name="members", value=vk)

def reset():
    S['current_motion'] = NO_MOTION
    S['member_in_question'] = None
    S['yays'] = 0
    S['nays'] = 0
    S.clear('positions')
