delegate_list = Variable()
masternode_list = Variable()
witness_list = Variable()
notifier_list = Variable()
scheduler_list = Variable()

num_boot_masternodes = Variable()
num_boot_delegates = Variable()

stamps_enabled = Variable()
nonces_enabled = Variable()



@construct
def seed(masternodes,
         delegates,
         num_boot_mns,
         num_boot_del,
         stamps=True,
         nonces=False):

    masternode_list.set(masternodes)
    delegate_list.set(delegates)
    witness_list.set([])
    notifier_list.set([])
    scheduler_list.set([])

    num_boot_masternodes.set(num_boot_mns)
    num_boot_delegates.set(num_boot_del)

    stamps_enabled.set(stamps)
    nonces_enabled.set(nonces)

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
def get_num_boot_masternodes():
    return num_boot_masternodes.get()

@export
def get_num_boot_delegates():
    return num_boot_delegates.get()


@export
def get_stamps_enabled():
    return stamps_enabled.get()


@export
def get_nonces_enabled():
    return nonces_enabled.get()
