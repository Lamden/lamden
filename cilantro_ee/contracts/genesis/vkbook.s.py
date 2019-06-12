del_list = Variable()
mn_list = Variable()

@construct
def seed(masternodes, delegates):
    mn_list.set(masternodes)
    del_list.set(delegates)


@export
def get_delegates():
    return del_list.get()


@export
def get_masternodes():
    return mn_list.get()


@export
def get_witnesses():
    return []
