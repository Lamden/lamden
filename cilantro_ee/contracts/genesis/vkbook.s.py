delegate_list = Variable()
masternode_list = Variable()
witness_list = Variable()
notifier_list = Variable()
scheduler_list = Variable()

masternode_quorum_max = Variable()
delegate_quorum_max = Variable()
masternode_quorum_min = Variable()
delegate_quorum_min = Variable()

stamps_enabled = Variable()
nonces_enabled = Variable()



@construct
def seed(masternodes,
         delegates,
         mn_quorum_min,
         del_quorum_min,
         stamps=True,
         nonces=False):

    masternode_list.set(masternodes)
    delegate_list.set(delegates)
    witness_list.set([])
    notifier_list.set([])
    scheduler_list.set([])

    mn_quorum_max = math.ceil(len(masternodes) * 2 / 3)
    del_quorum_max = math.ceil(len(delegates) * 2 / 3)

    masternode_quorum_max.set(mn_quorum_max)
    delegate_quorum_max.set(del_quorum_max)

    masternode_quorum_min.set(min(mn_quorum_min, mn_quorum_max))
    delegate_quorum_min.set(min(del_quorum_min, del_quorum_max))

    stamps_enabled.set(stamps)
    nonces_enabled.set(nonces)

@export
def get_delegates():
    return delegate_list.get()


@export
def get_masternodes():
    return masternode_list.get()


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
def get_masternode_quorum_max():
    return masternode_quorum_max.get()

@export
def get_delegate_quorum_max():
    return delegate_quorum_max.get()

@export
def get_masternode_quorum_min():
    return masternode_quorum_min.get()

@export
def get_delegate_quorum_min():
    return delegate_quorum_min.get()


@export
def get_stamps_enabled():
    return stamps_enabled.get()


@export
def get_nonces_enabled():
    return nonces_enabled.get()


@export
def get_fluctuating_quorum_enabled():
    return fluctuating_quorum_enabled.get()

