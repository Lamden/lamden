from cilantro.db.constants import VOTE_TYPES
from cilantro.db.db_manager import DBManager
from cilantro.proofs.pow import SHA3POW
from cilantro.transactions import TestNetTransaction
from cilantro.wallets import ED25519Wallet
from cilantro.interpreters.base_interpreter import BaseInterpreter
import hashlib


class BasicInterpreter(BaseInterpreter):
    """
    A basic interpreter capable of interpreting transaction objects and performing the necessary db updates, or raising
    an exception in the case that the transactions are infeasible
    Currently supports:
        - Standard transactions
        - Vote transactions
        - Stamp transactions
        - Swap transactions
        - Redeem transactions
    """

    def __init__(self, wallet=ED25519Wallet, proof_system=SHA3POW):
        super().__init__(wallet=wallet, proof_system=proof_system)
        self.db = DBManager()

    def interpret_transaction(self, transaction: TestNetTransaction):
        """
        Interprets the transaction, and updates scratch/balance state as necessary.
        If any validation fails (i.e. insufficient balance), this method will throw an error

        :param transaction: A TestNetTransaction object to interpret
        """
        self.transaction = transaction
        INTERPRETER_MAP = {TestNetTransaction.TX: self.interpret_std_tx,
                           TestNetTransaction.VOTE: self.interpret_vote_tx,
                           TestNetTransaction.STAMP: self.interpret_stamp_tx,
                           TestNetTransaction.SWAP: self.interpret_stamp_tx,
                           TestNetTransaction.REDEEM: self.interpret_redeem_tx}

        tx_payload = transaction.payload['payload']
        s = transaction.payload['metadata']['sig']

        if not TestNetTransaction.verify_tx(transaction=transaction.payload, verifying_key=tx_payload[1],
                                            signature=s, wallet=self.wallet,
                                            proof_system=self.proof_system)[0]:
            raise Exception("Interpreter could not verify transaction signature")

        print('(in interpret tx) transaction payload: {}'.format(tx_payload))  # debug line
        INTERPRETER_MAP[tx_payload[0]](tx_payload)

    def interpret_std_tx(self, tx_payload: tuple):
        sender = tx_payload[1]
        recipient = tx_payload[2]
        amount = float(tx_payload[3])

        if self.db.scratch.wallet_exists(sender):
            sender_balance = self.db.scratch.get_balance(sender)
            if sender_balance - amount >= 0:
                self.db.scratch.set_balance(sender, sender_balance - amount)
                self.__update_recipient_scratch(recipient, amount)
            else:
                raise Exception("Std Tx Error: sender does not have enough balance (against scratch)")
        else:
            balance = self.db.balance.get_balance(sender)
            if balance >= amount:
                self.db.scratch.set_balance(sender, balance - amount)
                self.__update_recipient_scratch(recipient, amount)
            else:
                raise Exception("Std Tx Error: sender does not have enough balance (against main balance)")

    def interpret_vote_tx(self, tx_payload: tuple):
        sender = tx_payload[1]
        candidate = tx_payload[2]

        self.db.votes.set_vote(sender, candidate, VOTE_TYPES.delegate)

    def interpret_stamp_tx(self, tx_payload: tuple):
        sender = tx_payload[1]
        amount = float(tx_payload[2])

        if amount > 0:
            sender_balance = self.db.balance.get_balance(sender)
            if sender_balance >= amount:
                sender_stamps = self.db.stamps.get_balance(sender)
                self.db.balance.set_balance(sender, sender_balance - amount)
                self.db.stamps.set_balance(sender, sender_stamps + amount)
            else:
                raise Exception("Stamp Tx Error: sender does not have enough balance (against main balance)")
        else:
            sender_stamps = self.db.stamps.get_balance(sender)
            if sender_stamps >= amount:
                sender_balance = self.db.balance.get_balance(sender)
                self.db.stamps.set_balance(sender, sender_stamps + amount)
                self.db.balance.set_balance(sender, sender_balance - amount)
            else:
                raise Exception("Stamp Tx Error: sender does not have enough balance (against stamps balance)")

    def interpret_swap_tx(self, tx_payload: tuple):
        sender, recipient, amount, hash_lock, unix_expiration = tx_payload[1:]
        amount = float(amount)

        sender_balance = self.db.balance.get_balance(sender)
        if sender_balance < amount:
            raise Exception("Swap Tx Error: sender does not have enough balance (against stamps balance)")

        if len(self.db.swaps.get_swap_data(hash_lock)) == 0:
            self.db.balance.set_balance(sender, sender_balance - amount)
            self.db.swaps.set_swap_data(hash_lock, sender, recipient, amount, unix_expiration)
        else:
            raise Exception("Swap Tx Error: hash lock {} already exists in swaps table".format(hash_lock))

    def interpret_redeem_tx(self, tx_payload: tuple):
        secret = bytes.fromhex(tx_payload[1])

        ripe = hashlib.new('ripemd160')
        ripe.update(secret)
        hash_lock = ripe.digest().hex()

        swap_tuple = self.db.swaps.get_swap_data(hash_lock)

        if len(swap_tuple) == 0:
            raise Exception("Redeem Tx Error: hash lock {} cannot be found in swap table swaps table".format(hash_lock))
        else:
            sig = self.transaction.payload['metadata']['sig']
            sender, recipient, amount, unix_expiration = swap_tuple
            amount = float(amount)
            msg = None
            if self.wallet.verify(recipient, msg, sig):
                # transfer funds
                recipient_balance = self.db.balance.get_balance(recipient)
                self.db.balance.set_balance(recipient, recipient_balance + amount)
                self.db.swaps.remove_swap_data(hash_lock)
            else:
                return Exception("Redeem Tx Error: could not verify sender signature")

    def __update_recipient_scratch(self, recipient, amount):
        """
        Helper method to increment the recipient's scratch balance by amount
        :param recipient: The key for the recipient in the scratch and main table
        :param amount: The amount to increment the recipient's scratch balance by
        """
        if self.db.scratch.wallet_exists(recipient):
            balance = self.db.scratch.get_balance(recipient)
        else:
            balance = self.db.balance.get_balance(recipient)
        self.db.scratch.set_balance(recipient, balance + amount)

