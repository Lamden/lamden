# A storage helper to create lists that are stored as hashes
# This will make maintaining large lists modify less state and as such, cost less stamps.

lists = Hash(default_value=None)

@export
def get_list(list_name: str, from_con_name: str = None):
    assert_called_by_contract()

    if from_con_name is None:
        con_name = ctx.caller
    else:
        con_name = from_con_name

    if not list_exists(con_name, list_name):
        return []

    limiter = lists[con_name, list_name, "limiter"]

    if limiter is None:
        return []

    l = []

    for i in range(limiter):
        l.append(lists[con_name, list_name, str(i)])

    return list(filter(not_deleted, l))

@export
def remove_by_index(list_name: str, index: int, from_con_name: str = None):
    assert_called_by_contract()
    con_name = get_con_name(from_con_name, list_name)
    assert_list_exists(con_name, list_name)

    limiter = lists[con_name, list_name, "limiter"]

    assert index < limiter, f'Index {index} out of max range {limiter - 1}.'

    prev_dels = count_prev_deletes(
        con_name=con_name,
        list_name="test_list",
        index=index
    )

    virtual_index = prev_dels + index

    assert virtual_index < limiter, f'Virtual index {virtual_index} out of max range {limiter - 1}.'

    lists[con_name, list_name, str(virtual_index)] = "__del__"

@export
def remove_by_value(list_name: str, value: int, remove_all: bool, from_con_name: str = None):
    assert_called_by_contract()
    con_name = get_con_name(from_con_name, list_name)
    assert_list_exists(con_name, list_name)

    limiter = lists[con_name, list_name, "limiter"]

    for i in range(limiter):
        if lists[con_name, list_name, str(i)] == value:
            lists[con_name, list_name, str(i)] = "__del__"

            if not remove_all:
                break

@export
def add_to_list(list_name: str, value: str, from_con_name: str = None):
    assert_called_by_contract()
    assert_reserved_values(value)
    con_name = get_con_name(from_con_name, list_name)

    if list_exists(con_name, list_name):
        limiter = lists[con_name, list_name, "limiter"]
    else:
        limiter = 1

    for i in range(limiter):
        if lists[con_name, list_name, str(i)] == "__del__":
            lists[con_name, list_name, str(i)] = value
            return

    lists[con_name, list_name, str(limiter)] = value
    lists[con_name, list_name, "limiter"] = limiter + 1

@export
def append_to_list(list_name: str, value: Any, from_con_name: str = None):
    assert_called_by_contract()
    assert_reserved_values(value)

    con_name = get_con_name(from_con_name, list_name)


    if list_exists(con_name, list_name):
        limiter = lists[con_name, list_name, "limiter"]
    else:
        limiter = 1

    lists[con_name, list_name, str(limiter)] = value
    lists[con_name, list_name, "limiter"] = limiter + 1

@export
def store_list(list_name: str, list_data: list, from_con_name: str = None):
    assert_called_by_contract()
    con_name = get_con_name(from_con_name, list_name)

    limiter = len(list_data)

    for i in range(limiter):
        if lists[con_name, list_name, str(i)] != list_data[i]:
            lists[con_name, list_name, str(i)] = list_data[i]

    lists[con_name, list_name, "limiter"] = limiter

@export
def approve(list_name: str, to: str):
    assert_called_by_contract()

    lists[ctx.caller, list_name, to] = True

@export
def revoke(list_name: str, to: str):
    assert_called_by_contract()

    lists[ctx.caller, list_name, to] = False

def not_deleted(value: Any):
    if value == "__del__":
        return False
    return True

def count_prev_deletes(con_name: str, list_name: str, index: int):
    dels = 0

    for i in range(index + 1):
        if lists[con_name, list_name, str(i)] == "__del__":
            dels = + 1

    return dels

def list_exists(con_name: str, list_name: str):
    return lists[con_name, list_name, "limiter"] is not None

def get_con_name(from_con_name: str, list_name: str):
    if from_con_name:
        assert_permission(from_con_name, list_name)
        return from_con_name
    else:
        return ctx.caller

@export
def assert_called_by_contract():
    assert ctx.caller[0:4] == "con_", "This method can only be called by contracts."

@export
def assert_permission(from_con_name: str, list_name: str):
    assert lists[from_con_name, list_name, ctx.caller], f'You do not have permission to modify list {from_con_name}:{list_name}.'

@export
def assert_list_exists(from_con_name: str, list_name: str):
    assert list_exists(from_con_name, list_name), f'List {from_con_name}:{list_name} does not exist.'

@export
def assert_reserved_values(value: Any):
    assert value is not "__del__", "Cannot add value '__del__' to a list."