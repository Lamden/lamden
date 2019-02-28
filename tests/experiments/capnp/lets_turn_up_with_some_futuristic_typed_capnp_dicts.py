import cilantro_ee
import capnp
import transaction_capnp
import secrets


d = {'bool key': True, 'a str key': 'hello', 'a bytes key': b'butt', 'an int key': 9000, 'a float key': 12.88883123112,
     'a binary blob': secrets.token_bytes(16)}


VALUE_TYPE_MAP = {
    str: 'text',
    bytes: 'data',
    bool: 'bool'
}


struct = transaction_capnp.ContractTransaction.new_message()
struct.payload.kwargs.init('entries', len(d))

for i, key in enumerate(d):
    value = d[key]
    struct.payload.kwargs.entries[i].key = key
    t = type(value)
    # Handle numerical values by casting them to strings
    if t in (int, float):
        struct.payload.kwargs.entries[i].value.fixedPoint = str(value)
    else:
        assert t in VALUE_TYPE_MAP, "value type {} not in dat map".format(t)
        setattr(struct.payload.kwargs.entries[i].value, VALUE_TYPE_MAP[t], value)


print("That good struct:\n{}".format(struct))
