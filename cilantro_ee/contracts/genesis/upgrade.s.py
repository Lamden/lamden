import election_house

# contract for network upgrade Supported features
#
# a) new update available (initiate_update)
# b) vote ready to switch (update_ready_vote)
# c) check for success/failure parameters (check_motion)


# possible votes

upg_lock = Variable() # network upgrade lock only one update can be performed
upg_init_time = Variable()
upg_pepper = Hash()
upg_window = Variable()

mn_vote = Variable()
dl_vote = Variable()


mn_rdy = Variable()
dl_rdy = Variable()

tot_mn = Variable()
tot_dl = Variable()

# Results
upg_consensus = Variable()
nw_ready = Variable()


@construct
def seed():
    upg_lock.set(False)

@export
def trigger_upgrade(pepper, initiator_vk):
    if upg_lock.get() is True:
        assert_parallel_upg_check()

    # for now only master's trigger upgrade
    if initiator_vk in election_house.current_value_for_policy('masternodes'):
        upg_lock.set(True)
        upg_init_time.set(now)
        upg_pepper.set(pepper)
        upg_window.set(datetime.Timedelta(seconds=3000000000))
        mn_vote.set(0)
        dl_vote.set(0)

        tot_mn.set(len(election_house.current_value_for_policy('masternodes')))
        tot_dl.set(len(election_house.current_value_for_policy('delegates')))

    else:
        return False


@export
def vote(vk):
    if upg_lock.get():
        if vk in election_house.current_value_for_policy('masternodes'):
            mn_vote.set(mn_vote.get() + 1)
        if vk in election_house.current_value_for_policy('delegates'):
            dl_vote.set(dl_vote.get() + 1)

        if now - upg_init_time.get() >= upg_window.get():
            reset_contract()

        if check_vote_state():
            reset_contract()

@export
def ready(vk):
    if upg_lock.get():
        if vk in election_house.current_value_for_policy('masternodes'):
            mn_rdy.set(mn_rdy.get() + 1)
        if vk in election_house.current_value_for_policy('delegates'):
            dl_rdy.set(dl_rdy.get() + 1)


def check_vote_state():
    required_mn = int((tot_mn.get() * 2) / 3)
    required_dl = int((tot_dl.get() * 2) / 3)

    if (mn_vote.get() > required_mn) and (dl_vote.get() > required_dl):
        upg_consensus.set(True)

    if (mn_rdy.get() > required_mn) and (dl_rdy.get() > required_dl):
        nw_ready.set(True)


def reset_contract():
    upg_init_time.set(None)
    upg_consensus.set(False)
    upg_lock.set(False)
    nw_ready.set(False)


def assert_parallel_upg_check():
    assert 'Upgrade under way. Cannot initiate parallel upgrade'
