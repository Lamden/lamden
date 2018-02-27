from cilantro.protocol.serialization import JSONSerializer
from cilantro.protocol.proofs import POW, SHA3POW
from cilantro.protocol.transactions import Transaction

TESTING = True
HOST = '127.0.0.1'
SUB_PORT = '8888'
SERIALIZER = JSONSerializer
PROOF = POW if TESTING else SHA3POW
PUB_PORT = '7878'
MASTERNODE_URL = 'http://testnet.lamden.io:8080'
GET_BALANCE_URL = MASTERNODE_URL + "/balance/all"
ADD_BLOCK_URL = MASTERNODE_URL + "/add_block"
GET_UPDATES_URL = MASTERNODE_URL + '/updates'
TRANSACTION = Transaction
INTERPRETER = None