masternode_list = Variable()
delegate_list = Variable()
witness_list = Variable()
notifier_list = Variable()
scheduler_list = Variable()

masternode_quorum_min = Variable()
delegate_quorum_min = Variable()
witness_quorum_min = Variable()
notifier_quorum_min = Variable()
scheduler_quorum_min = Variable()

stamps_enabled = Variable()
nonces_enabled = Variable()



@construct
def seed(masternodes,
         masternode_min_quorum,
         delegates,
         delegate_min_quorum=1,
         witnesses=[],
         witness_min_quorum=0,
         notifiers=[],
         notifier_min_quorum=0,
         schedulers=[],
         scheduler_min_quorum=0,
         enable_stamps=True,
         enable_nonces=False):

    masternode_list.set(masternodes)
    delegate_list.set(delegates)
    witness_list.set(witnesses)
    notifier_list.set(notifiers)
    scheduler_list.set(schedulers)

    masternode_quorum_min.set(masternode_min_quorum)
    delegate_quorum_min.set(delegate_min_quorum)
    witness_quorum_min.set(witness_min_quorum)
    notifier_quorum_min.set(notifier_min_quorum)
    scheduler_quorum_min.set(scheduler_min_quorum)

    stamps_enabled.set(enable_stamps)
    nonces_enabled.set(enable_nonces)

@export
def get_delegates():
    return delegate_list.get()


@export
def get_masternodes():
    return masternode_list.get()

@export
def check_master(vk):
    return vk in masternode_list.get()

@export
def check_delegate(vk):
    return vk in delegate_list.get()

@export
def get_witnesses():
    return witness_list.get()

@export
def get_notifiers():
    return notifier_list.get()


@export
def get_schedulers():
    return scheduler_list.get()

@export
def get_masternode_quorum_min():
    return masternode_quorum_min.get()

@export
def get_delegate_quorum_min():
    return delegate_quorum_min.get()

@export
def get_witness_quorum_min():
    return witness_quorum_min.get()

@export
def get_notifier_quorum_min():
    return notifier_quorum_min.get()

@export
def get_scheduler_quorum_min():
    return scheduler_quorum_min.get()


@export
def get_stamps_enabled():
    return stamps_enabled.get()


@export
def get_nonces_enabled():
    return nonces_enabled.get()
