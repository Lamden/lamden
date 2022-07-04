
def is_developer(contract: str):
    d = __Driver.get_var(contract=contract, variable='__developer__')
    return ctx.caller == d

@__export('stamp_forwarding')
def change_mode(contract: str, mode: str):
    assert is_developer(contract), 'Sender is not current developer!'
    assert mode in {'all', 'whitelist', 'blacklist'}, 'Invalid Mode!'

    __Driver.set_var(contract=contract,
                               variable='__stamps__.mode',
                               value=mode)

@__export('stamp_forwarding')
def enable(contract: str):
    assert is_developer(contract), 'Sender is not current developer!'

    __Driver.set_var(contract=contract,
                               variable='__stamps__.enabled',
                               value=True)

@__export('stamp_forwarding')
def disable(contract: str):
    assert is_developer(contract), 'Sender is not current developer!'

    __Driver.set_var(contract=contract,
                               variable='__stamps__.enabled',
                               value=None)


@__export('stamp_forwarding')
def add_to_whitelist(contract: str, address: str):
    assert is_developer(contract), 'Sender is not current developer!'

    __Driver.set_var(contract=contract,
                               variable=f'__stamps__.whitelist.{address}',
                               value=True)

@__export('stamp_forwarding')
def remove_from_whitelist(contract: str, address: str):
    assert is_developer(contract), 'Sender is not current developer!'

    __Driver.set_var(contract=contract,
                               variable=f'__stamps__.whitelist.{address}',
                               value=None)


@__export('stamp_forwarding')
def add_to_blacklist(contract: str, address: str):
    assert is_developer(contract), 'Sender is not current developer!'

    __Driver.set_var(contract=contract,
                               variable=f'__stamps__.blacklist.{address}',
                               value=True)


@__export('stamp_forwarding')
def remove_from_blacklist(contract: str, address: str):
    assert is_developer(contract), 'Sender is not current developer!'

    __Driver.set_var(contract=contract,
                               variable=f'__stamps__.blacklist.{address}',
                               value=None)
