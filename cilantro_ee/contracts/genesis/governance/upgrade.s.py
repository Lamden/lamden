import vkbook
import datetime

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
def init_upgrade(pepper, initiator_vk):
    if upg_lock.get() is True:
        assert_parallel_upg_check()

    if vkbook.check_master(initiator_vk) or vkbook.check_delegate(initiator_vk):
        upg_lock.set(True)
        upg_init_time.set(datetime.now)
        upg_pepper.set(pepper)
        upg_window.set(datetime.second(30))
        upg_consensus.set(False)
        mn_vote.set(0)
        dl_vote.set(0)

@export
def vote(vk):
    if upg_lock.get():
        if vkbook.check_master(vk):
            mn_vote.set(mn_vote.get() + 1)
        if vkbook.check_delegate(vk):
            dl_vote.set(dl_vote.get() + 1)

        if datetime.now - upg_init_time.get() >= upg_window.get():
            reset_contract()
            raise Exception('Failed to get quorum nodes for upgrade')

        if check_vote_state():
            reset_contract()


def check_vote_state():
    mn = vkbook.get_masternodes()
    dl = vkbook.get_delegates()

    if (mn_vote > (mn*2)/3) and (dl_vote > (dl*2)/3):
        upg_consensus.set(True)
        return True
    else:
        return False


def reset_contract():
    upg_init_time.set(None)
    upg_lock.set(False)


def assert_parallel_upg_check():
    assert 'Upgrade under way. Cannot initiate parallel upgrade'
