del_list = Variable()
mn_list = Variable()
metering_flag = Variable()
nonce_flag = Variable()

@construct
def seed(masternodes, delegates, metering=True, nonces=False):
    mn_list.set(masternodes)
    del_list.set(delegates)
    metering_flag.set(metering)
    nonce_flag.set(nonces)

@export
def get_delegates():
    return del_list.get()


@export
def get_masternodes():
    return mn_list.get()


@export
def get_witnesses():
    return []

