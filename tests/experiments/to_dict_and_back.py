from cilantro_ee.messages.transaction.data import TransactionDataBuilder, TransactionData

import capnp
import transaction_capnp

tx = TransactionDataBuilder.create_random_tx()
print(tx)


struct = tx._data
d = tx._data.to_dict()

print("dict from struct: {}".format(d))
print("\n\n")

rebuilt = transaction_capnp.TransactionData.new_message(**d)

print("rebiult data: {}".format(rebuilt))