from cilantro_ee.messages import capnp as schemas
import os
import capnp

envelope_capnp = capnp.load(os.path.dirname(schemas.__file__) + '/envelope.capnp')

e = envelope_capnp.Message.new_message()

e.payload = b'poo'

print(e.to_bytes_packed())
