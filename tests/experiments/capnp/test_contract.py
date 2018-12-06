from cilantro.messages.transaction.contract import ContractTransaction
import cilantro.protocol.wallet as wallet

# Create a transaction
sk, vk = wallet.new()
nonce = vk + ':' + '0'*64
tx = ContractTransaction.create(sender_sk=sk, stamps_supplied=1000, contract_name='currency', func_name='transfer',
                                nonce=nonce, to='colin', amount=9000)

# Look at the underlying struct
print("Original struct:")
print(type(tx._data))  # type is <class 'capnp.lib.capnp._DynamicStructBuilder'>
print(tx._data)

# Create a 'clone' from the transaction's binary data.
clone = ContractTransaction.from_bytes(tx.serialize())

print("\n\n")

# Look at the clone
print("Reconstructed struct:")
print(type(clone._data))  # type is <class 'capnp.lib.capnp._DynamicStructReader'>
print(clone._data)

print("\n\n")

# Manually check clones signature
sender = clone._data.payload.sender.decode()
signature = clone._data.metadata.signature.decode()
payload_bin = clone._data.payload.as_builder().copy().to_bytes()
is_valid_sig = wallet.verify(sender, payload_bin, signature)
print("is valid sig: ", is_valid_sig)
