from cilantro.protocol.serialization import JSONSerializer
from cilantro.protocol.proofs import SHA3POW
from cilantro.protocol.wallets import ED25519Wallet
from cilantro.protocol.interpreters import vanilla as VanillaInterpreter

WALLET = ED25519Wallet
SERIALIZER = JSONSerializer
PROOF = SHA3POW
INTERPRETER = VanillaInterpreter
