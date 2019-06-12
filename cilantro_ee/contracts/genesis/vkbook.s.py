delegates = Variable()
masternodes = Variable()

@construct
def seed():
    masternodes.set([
        "044144c0531e16e327a63707fc2a0ec04557b94bdb1e0d4b05528cda20372374",
        "ea02ff596edf98233291ae8b8580ce16af1d583f68d86003bc8dd87e353109f5",
    ])

    delegates.set([
        "6351af77b096c67898ccd1bd29b97b9959af66c95b5265b5316fe6bdd3378bac",
        "71a0f5ecec9a582d809cd22a89e0acedba04a844b9ce7faa9c2f6ff96e3177ed",
    ])


@export
def get_delegates():
    return delegates.get()


@export
def get_masternodes():
    return masternodes.get()


@export
def get_witnesses():
    return []
