import vkbook

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

# Results
upg_consensus = Variable()

@construct
def seed():
    upg_lock.set(False)

@export
def init_upgrade(pepper, vk):
    if check_master(vk) or check_delegate(vk):
        upg_lock.set(True)
        upg_init_time.set(now)
        upg_pepper.set(pepper)
        upg_window.set(datetime.second(30))
        upg_consensus.set(False)
        mn_vote.set(0)
        dl_vote.set(0)

@export
def vote(vk):
    if upg_lock.get():
        if check_master(vk):
            mn_vote = mn_vote.get() + 1
            mn_vote.set(mn_vote)
        if check_delegate(vk):
            dl_vote = dl_vote.get() + 1
            dl_vote.set(dl_vote)

        if now - upg_init_time.get() >= upg_window.get():
            reset_contract()
            raise Exception('Failed to get quorum nodes for upgrade')

        if check_vote_state():
            reset_contract()


def check_vote_state():
    mn = get_masternodes()
    dl = get_delegates()

    if (mn_vote > (mn*2)/3) and (dl_vote > (dl*2)/3):
        upg_consensus.set(True)
        return True
    else:
        return False


def reset_contract():
    upg_init_time.set(None)
    upg_lock.set(False)
