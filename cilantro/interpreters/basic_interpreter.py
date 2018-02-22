from cilantro.db.constants import VOTE_TYPES
from cilantro.db.delegate.driver_manager import DriverManager
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

    def __init__(self, wallet=ED25519Wallet, proof_system=SHA3POW, initial_state: dict=None):
        super().__init__(wallet=wallet, proof_system=proof_system)
        self.db = DriverManager()

        if initial_state:
            print("Seeding initial state...")
            self.db.balance.seed_state(initial_state)
            print("Done seeding state with {} wallets.".format(len(initial_state)))

    def update_state(self, state: dict):
        print("Interpreter flushing scratch...")
        self.db.scratch.flush()
        print("Interpreter setting new balances for {} wallets...".format(len(state)))
        self.db.balance.seed_state(state)
        print("Interpreter done updating state.")

    def interpret_transaction(self, transaction: TestNetTransaction):
        """
        Interprets the transaction, and updates scratch/balance state as necessary.
        If any validation fails (i.e. insufficient balance), this method will raise an exception

        :param transaction: A TestNetTransaction object to interpret
        """
        self.transaction = transaction
        INTERPRETER_MAP = {TestNetTransaction.TX: self.interpret_std_tx,
                           TestNetTransaction.VOTE: self.interpret_vote_tx,
                           TestNetTransaction.STAMP: self.interpret_stamp_tx,
                           TestNetTransaction.SWAP: self.interpret_swap_tx,
                           TestNetTransaction.REDEEM: self.interpret_redeem_tx}

        tx_payload = transaction.payload['payload']
        s = transaction.payload['metadata']['signature']
        payload_binary = TestNetTransaction.SERIALIZER.serialize(tx_payload)

        if not TestNetTransaction.verify_tx(transaction=transaction.payload, verifying_key=tx_payload[1],
                                            signature=s, wallet=self.wallet,
                                            proof_system=self.proof_system)[0]:
            raise Exception("Interpreter could not verify transaction signature")

        # print('(in interpret tx) transaction payload: {}'.format(tx_payload))  # debug line
        INTERPRETER_MAP[tx_payload[0]](tx_payload[1:])

    def interpret_std_tx(self, tx_payload: tuple):
        sender = tx_payload[0]
        recipient = tx_payload[1]
        amount = float(tx_payload[2])
        sender_balance = self.__get_balance(sender)

        if sender_balance >= amount:
            self.db.scratch.set_balance(sender, sender_balance - amount)
            self.__update_scratch(recipient, amount)
        else:
            raise Exception("Standard Tx Error: sender does not have enough balance "
                            "(balance={} but attempted to send {}".format(sender_balance, amount))

    def interpret_vote_tx(self, tx_payload: tuple):
        sender = tx_payload[0]
        candidate = tx_payload[1]

        self.db.votes.set_vote(sender, candidate, VOTE_TYPES.delegate)

    def interpret_stamp_tx(self, tx_payload: tuple):
        """
        Executes a stamp transaction. If amount is positive, this will subtract the amount from the sender's scratch
        and add it to his stamp balance (balance --> stamps). If amount is negative, this will subtract the
        amount from sender's stamps and add it to his balance (stamps --> balance).

        :param tx_payload: A tuple specifying (sender, amount)
        """
        sender = tx_payload[0]
        amount = float(tx_payload[1])

        if amount > 0:
            # Transfer balance to stamps
            sender_balance = self.__get_balance(sender)
            if sender_balance >= amount:
                sender_stamps = self.db.stamps.get_balance(sender)
                self.__update_scratch(sender, -amount)
                self.db.stamps.set_balance(sender, sender_stamps + amount)
            else:
                raise Exception("Stamp Tx Error: sender does not have enough balance (against main balance)")
        else:
            # Transfer stamps to balance
            sender_stamps = self.db.stamps.get_balance(sender)
            if sender_stamps >= -amount:
                self.db.stamps.set_balance(sender, sender_stamps + amount)
                self.__update_scratch(sender, -amount)
            else:
                raise Exception("Stamp Tx Error: sender does not have enough balance (against stamps balance)")

    def interpret_swap_tx(self, tx_payload: tuple):
        sender, recipient, amount, hash_lock, unix_expiration = tx_payload
        amount = float(amount)
        sender_balance = self.__get_balance(sender)

        if sender_balance < amount:
            raise Exception("Swap Tx Error: sender does not have enough balance")

        if not self.db.swaps.swap_exists(hash_lock): #len(self.db.swaps.get_swap_data(hash_lock)) == 0:
            self.__update_scratch(sender, -amount)
            self.db.swaps.set_swap_data(hash_lock, sender, recipient, amount, unix_expiration)
        else:
            raise Exception("Swap Tx Error: hash lock {} already exists in swaps table".format(hash_lock))

    def interpret_redeem_tx(self, tx_payload: tuple):
        tx_sender = tx_payload[0]
        secret = bytes.fromhex(tx_payload[1])
        # TODO -- unpack timestamp once this gets added in Masternode

        ripe = hashlib.new('ripemd160')
        ripe.update(secret)
        hash_lock = ripe.digest().hex()

        if not self.db.swaps.swap_exists(hash_lock):
            raise Exception("Redeem Tx Error: hash lock {} cannot be found in swap table swaps table".format(hash_lock))

        sender, recipient, amount, unix_expiration = self.db.swaps.get_swap_data(hash_lock)
        amount = float(amount)
        sig = self.transaction.payload['metadata']['signature']
        msg = TestNetTransaction.SERIALIZER.serialize(self.transaction.payload['payload'])

        if tx_sender not in (sender, recipient):
            raise Exception("Redeem Tx Error: redemption attempted by actor who is neither the original"
                            " sender nor recipient (tx sender={}".format(tx_sender))
        if not (self.wallet.verify(sender, msg, sig) or self.wallet.verify(recipient, msg, sig)):
            raise Exception("Redeem Tx Error: signature could not be verified as either original sender or recipient")

        if tx_sender == recipient:
            # Execute swap
            self.__update_scratch(recipient, amount)
            self.db.swaps.remove_swap_data(hash_lock)
        elif tx_sender == sender:
            # TODO -- add a check here to see if the swap tx is past expiration
            if (True):
                # Swap is past expiration, refund original sender
                self.__update_scratch(sender, amount)
                self.db.swaps.remove_swap_data(hash_lock)
            else:
                # Swap is not past expiration
                raise Exception("Redeem Tx Error: sender attempted to redeem swap that is not past expiration")

    def __update_scratch(self, address, amount):
        """
        Helper method to increment the recipient's scratch balance by amount. A negative value for amount will decrement
        recipient's scratch balance.

        :param address: The key for the address in the scratch/main balance table
        :param amount: If positive, the amount to increment the address' scratch balance by. If negative, the address'
        balance will be decremented by this amount
        """
        balance = self.__get_balance(address)
        self.db.scratch.set_balance(address, balance + amount)

    def __get_balance(self, address) -> float:
        """
        Helper method to get the balance for address if it is in scratch, or main balance if the address does not
        exist in scratch

        :param address: The key to retrieve the balance for
        :return: The balance of the address
        """
        if self.db.scratch.wallet_exists(address):
            return self.db.scratch.get_balance(address)
        else:
            return self.db.balance.get_balance(address)

