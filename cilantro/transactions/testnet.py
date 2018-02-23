from cilantro.transactions import Transaction
from cilantro.wallets import Wallet, ED25519Wallet
from cilantro.proofs.pow import POW
from cilantro.serialization.json_serializer import JSONSerializer


class TestNetTransaction(Transaction):
    # old dictionary based payload
    # payload_format = {
    #     'payload' : None,
    #     'metadata' : {
    #         'signature' : None,
    #         'proof' : None
    #     }
    # }

    # payload is now in tuple format instead of dictionary - comes from JSON as an array (list)
    tesnet_tx_format = {
        'metadata' : {'proof' : None,
                      'signature' : None},

        'payload' : ['type', 'sender', 'recipient', 'amount']
    }

    # transaction types (first entry of payload array)
    TX = 't'
    STAMP = 's'
    VOTE = 'v'
    SWAP = 'a'
    REDEEM = 'r'

    SERIALIZER = JSONSerializer

    # example of tesnet transaction JSON that is POSTed to locahost 8080
    '''
    {"metadata": {"proof": "7b707d7e1c92fdf7a0195852f26346d3",
  "signature": "fdb7a1d9dd34121e4005c8cb9dcfcd0217d9245158dfad71dbea0538fcdb23a43ac0c952263ed08d966d8db1d1d655b3178edf14ba91a35ff52b44dec8807b0f"},
 "payload": ["t",
  "260e707fa8e835f2df68f3548230beedcfc51c54b486c7224abeb8c7bd0d0d8f",
  "f7947784333851ec363231ade84ca63b21d03e575b1919f4042959bcd3c89b5f",
  "4"]}
    '''

    @staticmethod
    def validate_tx_fields(tx: dict) -> bool:
        """
        Attempts to validate the transaction fields, and throws and error if any fields are missing. If
        the fields are valid, this method returns true
        :param tx: A transaction dictionary, assumed to be in the same form as it would be in a user's initial POST
        request to Masternode
        :return: True if the transaction fields are valid
        :raises: An exception if an invalid or missing field is found
        """

        pd = tx['payload']  # testnet transaction payload field only

        # check tx payload type
        if not pd[0] == 't':
            raise ValueError('Tesnet transaction type should be standard only')

        # check tx payload tuple length
        if not len(pd) == 4:
            raise ValueError('Tesnet standard transaction should strictly include 4 elements')

        # check sender is valid hex - fastest
        try:
            int(pd[1], 16)
        except ValueError:
            raise ValueError('Tesnet send address must be valid hexadecimal')

        # check sender length is valid
        if not len(pd[1]) == 64:
            raise ValueError('Tesnet send address must be 64 characters long')

        # check receiver is valid hex - fastest
        try:
            int(pd[2], 16)
        except ValueError:
            raise ValueError('Tesnet receiver address must be valid hexadecimal')

        # check receiver length is valid
        if not len(pd[2]) == 64:
            raise ValueError('Tesnet receiver address must be 64 characters long')

        # check tx amount type is numeric
        try:
            float(pd[3])
        except ValueError:
            raise ValueError('Tesnet transaction amount must resolve to numeric')

        # check tx amount is non-negative
        if not float(pd[3]) >= 0:
            raise ValueError('Testnet transaction amount must be non-negative')

        return True  # transaction payload is valid



        # def build_exception(message: str) -> Exception:
        #     return Exception("Transaction Validation Failed -- {}\nfor transaction Dictionary: {}"
        #                      .format(message, tx))
        #
        # def check_fields(fields: tuple, d: dict):
        #     for field in fields:
        #         if field not in d:
        #             raise build_exception("field {} missing".format(field))
        #
        # # Basic type checks
        # if tx == None:
        #     raise TypeError('Transaction Validation Failed -- tx_dict is None')
        # elif type(tx) is not dict:
        #     raise TypeError('Transaction Validation Failed -- tx_dict is of wrong type')
        #
        # # payload/metadata field checks
        # if 'payload' not in tx:
        #     raise build_exception('payload field missing')
        # elif 'metadata' not in tx:
        #     raise build_exception('metadata field is missing')
        #
        # payload = tx['payload']
        # metadata = tx['metadata']
        #
        # # metadata checks
        # if 'signature' not in metadata:
        #     raise build_exception('signature field missing from metadata')
        # elif 'proof' not in metadata:
        #     raise build_exception('proof field missing from metadata')
        #
        # # payload checks
        # if 'type' not in payload:
        #     raise build_exception('type field missing from payload')
        # elif payload['type'] not in (TestNetTransaction.TX, TestNetTransaction.STAMP, TestNetTransaction.VOTE,
        #                              TestNetTransaction.SWAP, TestNetTransaction.REDEEM):
        #     raise build_exception('invalid type {} in payload'.format(payload['type']))
        #
        # # Check required fields for each transaction type
        # if payload['type'] == TestNetTransaction.TX:
        #     check_fields(('to', 'from', 'amount'), payload)
        # elif payload['type'] == TestNetTransaction.STAMP:
        #     check_fields(('from', 'amount'), payload)
        # elif payload['type'] == TestNetTransaction.VOTE:
        #     check_fields(('from', 'to'), payload)
        # elif payload['type'] == TestNetTransaction.SWAP:
        #     check_fields(('from', 'to', 'amount', 'hash_lock', 'unix_expiration'), payload)
        # elif payload['type'] == TestNetTransaction.REDEEM:
        #     check_fields(('redeem', 'redeem'), payload)
        #
        # return True


    @staticmethod
    def standard_tx(sender: str, to: str, amount: str):
        return [TestNetTransaction.TX, sender, to, amount]

    @staticmethod
    def stamp_tx(sender: str, amount):
        return [TestNetTransaction.STAMP, sender, amount]

    @staticmethod
    def vote_tx(sender: str, address):
        return [TestNetTransaction.VOTE, sender, address]

    @staticmethod
    def swap_tx(sender: str, recipient: str, amount: str, hash_lock: str, unix_expiration: str):
        return [TestNetTransaction.SWAP, sender, recipient, amount, hash_lock, unix_expiration]

    @staticmethod
    def redeem_tx(sender: str, secret: str):
        return [TestNetTransaction.REDEEM, sender, secret]

    @staticmethod
    def verify_tx(transaction, verifying_key, signature, wallet: Wallet, proof_system: POW):
        payload_binary = TestNetTransaction.SERIALIZER.serialize(transaction['payload'])
        valid_signature = wallet.verify(verifying_key, payload_binary, signature)
        try:
            valid_proof = proof_system.check(payload_binary, transaction['metadata']['proof'][0])
        except:
            valid_proof = transaction['metadata']['proof'] == 's'
        return valid_signature, valid_proof

    @staticmethod
    def from_dict(tx_dict, wallet=ED25519Wallet, proof=POW):
        """
        Build a TestNetTransaction object from a dictionary.
        :param tx_dict: A dictionary containing the transaction data
        :param wallet: Wallet to use for transaction
        :param proof: Proof algorithm to use for transaction
        :return: A TestNetTransaction object
        """
        transaction = TestNetTransaction(wallet, proof)
        transaction.payload['metadata'] = tx_dict['metadata']

        payload = tx_dict['payload']

        tx_type = payload[0]

        if tx_type == TestNetTransaction.TX:
            sender, receiver, amount = payload[1], payload[2], str(payload[3])
            transaction.payload['payload'] = TestNetTransaction.standard_tx(sender, receiver, amount)
        elif tx_type == TestNetTransaction.STAMP:
            sender, amount = payload[1], payload[2]
            transaction.payload['payload'] = TestNetTransaction.stamp_tx(sender, amount)
        elif tx_type == TestNetTransaction.VOTE:
            sender, receiver = payload[1], payload[2]
            transaction.payload['payload'] = TestNetTransaction.vote_tx(sender, receiver)
        elif tx_type == TestNetTransaction.SWAP:
            sender, receiver, amount, hash_lock, unix_expir = payload[1], payload[2], str(payload[3]), \
                                                              payload[4], payload[5]
            transaction.payload['payload'] = TestNetTransaction.swap_tx(sender, receiver, amount, hash_lock, unix_expir)
        elif tx_type == TestNetTransaction.REDEEM:
            transaction.payload['payload'] = TestNetTransaction.redeem_tx(payload[1], payload[2])
        else:
            raise Exception('Error building transaction from dict -- '
                            'Invalid type field in transaction dict: {}'.format(tx_dict))

        return transaction

    def __init__(self, wallet, proof):
        super().__init__(wallet, proof)
        self.payload = {
                'payload' : None,
                'metadata' : {
                    'signature' : None,
                    'proof' : None
                }
            }

    def build(self, tx, s, use_stamp=False, complete=True):
        self.payload['payload'] = tx

        if complete:
            self.payload['metadata']['signature'] = self.sign(s)
            if use_stamp:
                self.payload['metadata']['proof'] = TestNetTransaction.STAMP
            else:
                self.payload['metadata']['proof'] = self.seal()

    def sign(self, s):
        return self.wallet.sign(s, TestNetTransaction.SERIALIZER.serialize(self.payload['payload']))

    def seal(self):
        return self.proof_system.find(TestNetTransaction.SERIALIZER.serialize(self.payload['payload']))
