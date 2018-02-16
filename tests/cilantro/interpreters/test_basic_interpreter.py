from unittest import TestCase
from unittest.mock import MagicMock, call, patch
from cilantro.interpreters.basic_interpreter import BasicInterpreter
from cilantro.wallets import ED25519Wallet
from cilantro.transactions.testnet import TestNetTransaction
from cilantro.proofs.pow import SHA3POW
from cilantro.db.constants import *
import secrets, hashlib


REMOVED_HASH_ID = '999'  # for mocking removed hash locks


def hash_ripe(secret):
    h = hashlib.new('ripemd160')
    h.update(bytes.fromhex(secret))
    return h.digest().hex()


@patch('cilantro.interpreters.basic_interpreter.DriverManager')
def build_interpreter(state: dict, db: MagicMock):
    interpreter = BasicInterpreter()
    interpreter.db = db

    if SCRATCH_KEY not in state:
        state[SCRATCH_KEY] = {}
    if SWAP_KEY not in state:
        state[SWAP_KEY] = {}

    for d in [interpreter.db.balance, interpreter.db.scratch, interpreter.db.votes,
              interpreter.db.stamps, interpreter.db.swaps]:
        d = MagicMock()

    interpreter.db.balance.get_balance = MagicMock(side_effect=lambda k: state[BALANCE_KEY][k]
                                                   if ((BALANCE_KEY in state) and (k in state[BALANCE_KEY])) else 0)
    interpreter.db.scratch.get_balance = MagicMock(side_effect=lambda k: state[SCRATCH_KEY][k])
    interpreter.db.scratch.wallet_exists = MagicMock(side_effect=lambda k: k in state[SCRATCH_KEY])
    interpreter.db.stamps.get_balance = MagicMock(side_effect=lambda k: state[STAMP_KEY][k]
                                                  if ((STAMP_KEY in state) and (k in state[STAMP_KEY])) else 0)
    interpreter.db.swaps.get_swap_data = MagicMock(side_effect=lambda k: state[SWAP_KEY][k]
                                                   if ((SWAP_KEY in state) and (k in state[SWAP_KEY])) else ())
    interpreter.db.swaps.swap_exists = MagicMock(side_effect=lambda k: k in state[SWAP_KEY])

    return interpreter


def assert_state_updates(interpreter, state):
    def calls_for_key(key):
        return [call(wallet_key, balance) for wallet_key, balance in state[key].items()]

    if BALANCE_KEY in state:
        interpreter.db.balance.set_balance.assert_has_calls(calls_for_key(BALANCE_KEY), any_order=True)

    if SCRATCH_KEY in state:
        interpreter.db.scratch.set_balance.assert_has_calls(calls_for_key(SCRATCH_KEY), any_order=True)

    if STAMP_KEY in state:
        interpreter.db.stamps.set_balance.assert_has_calls(calls_for_key(STAMP_KEY), any_order=True)

    if SWAP_KEY in state:
        set_calls, del_calls = [], []
        for hash_lock, t in state[SWAP_KEY].items():
            del_calls.append(call(hash_lock)) if t == REMOVED_HASH_ID else set_calls.append(call(hash_lock, *t))
        interpreter.db.swaps.set_swap_data.assert_has_calls(set_calls, any_order=True)
        interpreter.db.swaps.remove_swap_data.assert_has_calls(del_calls, any_order=True)

    if VOTE_KEY in state:
        set_calls = []
        for vote_type in state[VOTE_KEY]:
            for sender, candidate in state[VOTE_KEY][vote_type].items():
                set_calls.append(call(sender, candidate, vote_type))
        interpreter.db.votes.set_vote.assert_has_calls(set_calls, any_order=True)


def test_interpreter(tx, config_state, post_state):
    interpreter = build_interpreter(config_state)
    interpreter.interpret_transaction(tx)
    assert_state_updates(interpreter, post_state)
    return interpreter


def build_std_tx(amount, use_stamp=False, complete=True):
    sender_s, sender_v = ED25519Wallet.new()
    receiver_s, receiver_v = ED25519Wallet.new()
    tx = TestNetTransaction(ED25519Wallet, SHA3POW)
    tx.build(TestNetTransaction.standard_tx(sender_v, receiver_v, str(amount)), sender_s, use_stamp=use_stamp,
             complete=complete)
    return sender_v, receiver_v, tx


def build_stamp_tx(amount):
    sender_s, sender_v = ED25519Wallet.new()
    tx = TestNetTransaction(ED25519Wallet, SHA3POW)
    tx.build(TestNetTransaction.stamp_tx(sender_v, str(amount)), sender_s)
    return sender_v, tx


def build_swap_tx(amount, unix_expir, secret=None):
    sender_s, sender_v = ED25519Wallet.new()
    receiver_s, receiver_v = ED25519Wallet.new()
    tx = TestNetTransaction(ED25519Wallet, SHA3POW)

    if secret is None:
        secret = secrets.token_hex(16)
    hash_lock = hash_ripe(secret)

    tx.build(TestNetTransaction.swap_tx(sender_v, receiver_v, amount, hash_lock, unix_expir), sender_s)
    return sender_v, receiver_v, hash_lock, tx


class TestBasicInterpreter(TestCase):

    def test_invalid_sig(self):
        """
        Tests that an error is raised when trying to interpret a transaction with an invalid signature
        """
        sender_s, sender_v = ED25519Wallet.new()
        receiver_s, receiver_v = ED25519Wallet.new()
        tx = TestNetTransaction(ED25519Wallet, SHA3POW)
        tx.build(TestNetTransaction.standard_tx(sender_v, receiver_v, '100'), receiver_v)
        interpreter = build_interpreter({})

        self.assertRaises(Exception, interpreter.interpret_transaction, tx)

    def test_std_valid_in_scratch(self):
        """
        Tests a valid standard transaction, where both the sender and recipient exist in the scratch
        """
        amount = 100
        sender_scratch = 1000
        receiver_scratch = 500
        sender, receiver, tx = build_std_tx(amount)

        config_state = {SCRATCH_KEY: {sender: sender_scratch, receiver: receiver_scratch}}
        post_state = {SCRATCH_KEY: {sender: sender_scratch - amount, receiver: receiver_scratch + amount}}

        test_interpreter(tx, config_state, post_state)

    def test_std_valid_recipient_no_scratch(self):
        """
        Tests a valid standard transaction, where the sender exists in scratch the but the recipient does not
        """
        amount = 100
        sender_scratch = 1000
        receiver_balance = 500
        sender, receiver, tx = build_std_tx(amount)

        config_state = {SCRATCH_KEY: {sender: sender_scratch}, BALANCE_KEY: {receiver: receiver_balance}}
        post_state = {SCRATCH_KEY: {sender: sender_scratch - amount, receiver: receiver_balance + amount}}

        test_interpreter(tx, config_state, post_state)

    def test_std_valid_sender_no_scratch(self):
        """
        Tests a valid standard transaction, where the receiver exists in scratch the but the sender does not
        """
        amount = 100
        sender_balance = 1000
        receiver_scratch = 500
        sender, receiver, tx = build_std_tx(amount)

        config_state = {SCRATCH_KEY: {receiver: receiver_scratch}, BALANCE_KEY: {sender: sender_balance}}
        post_state = {SCRATCH_KEY: {sender: sender_balance - amount, receiver: receiver_scratch + amount}}

        test_interpreter(tx, config_state, post_state)

    def test_std_valid_no_scratch(self):
        """
        Tests a valid standard transaction, where neither the receiver not the sender is in the scratch
        :return:
        """
        amount = 100
        sender_balance = 1000
        receiver_balance = 500
        sender, receiver, tx = build_std_tx(amount)

        config_state = {BALANCE_KEY: {sender: sender_balance, receiver: receiver_balance}}
        post_state = {SCRATCH_KEY: {sender: sender_balance - amount, receiver: receiver_balance + amount}}

        test_interpreter(tx, config_state, post_state)

    def test_std_valid_complete_drain(self):
        """
        Tests a valid standard transaction where the sender sends the entirety of his balance to the recipient
        """
        amount = 1000
        sender_balance = 1000
        receiver_balance = 500
        sender, receiver, tx = build_std_tx(amount)

        config_state = {BALANCE_KEY: {sender: sender_balance, receiver: receiver_balance}}
        post_state = {SCRATCH_KEY: {sender: sender_balance - amount, receiver: receiver_balance + amount}}

        test_interpreter(tx, config_state, post_state)

    def test_std_invalid_no_balance(self):
        """
        Tests an invalid standard transaction where neither the sender nor receiver exist in the balance
        (and thus the sender should have insufficient funds)
        """
        amount = 100
        sender, receiver, tx = build_std_tx(amount)

        interpreter = build_interpreter({})

        self.assertRaises(Exception, interpreter.interpret_transaction, tx)

    def test_std_invalid_insufficient_balance(self):
        """
        Tests an invalid standard transaction where the sender does not have enough funds
        """
        amount = 2000
        sender_balance = 1000
        receiver_balance = 500
        sender, receiver, tx = build_std_tx(amount)

        config_state = {BALANCE_KEY: {sender: sender_balance, receiver: receiver_balance}}
        interpreter = build_interpreter(config_state)
        self.assertRaises(Exception, interpreter.interpret_transaction, tx)

    def test_std_invalid_insufficient_scratch(self):
        """
        Tests an invalid standard transaction where the sender does not have enough funds in scratch, but enough in
        balance
        """
        amount = 2000
        sender_balance = 5000
        sender_scratch = 1000
        receiver_balance = 500
        sender, receiver, tx = build_std_tx(amount)

        config_state = {BALANCE_KEY: {sender: sender_balance, receiver: receiver_balance},
                        SCRATCH_KEY: {sender: sender_scratch}}
        interpreter = build_interpreter(config_state)
        self.assertRaises(Exception, interpreter.interpret_transaction, tx)

    def test_vote(self):
        """
        Tests a valid vote transaction
        """
        sender_s, sender_v = ED25519Wallet.new()
        receiver_s, receiver_v = ED25519Wallet.new()
        tx = TestNetTransaction(ED25519Wallet, SHA3POW)
        tx.build(tx.vote_tx(sender_v, receiver_v), sender_s)
        post_state = {VOTE_KEY: {VOTE_TYPES.delegate: {sender_v: receiver_v}}}

        interpreter = build_interpreter({})
        interpreter.interpret_transaction(tx)

        assert_state_updates(interpreter, post_state)

    def test_stamp_valid_to_balance_no_stamps(self):
        """
        Tests a valid stamp transaction where the sender converts some amount of his balance to stamps. Sender does not
        exist in scratch, and has no stamps.
        """
        stamp_amount = 100
        sender_balance = 200
        sender, tx = build_stamp_tx(stamp_amount)

        config_state = {BALANCE_KEY: {sender: sender_balance}}
        post_state = {STAMP_KEY: {sender: stamp_amount}, SCRATCH_KEY: {sender: sender_balance - stamp_amount}}

        test_interpreter(tx, config_state, post_state)

    def test_stamp_valid_to_balance_some_stamps(self):
        """
        Tests a valid stamp transaction where the sender converts some amount of his balance to stamps. Sender exists
        in scratch, and has some stamps.
        """
        stamp_amount = 100
        sender_stamps = 50
        sender_balance = 200
        sender, tx = build_stamp_tx(stamp_amount)

        config_state = {SCRATCH_KEY: {sender: sender_balance}, STAMP_KEY: {sender: sender_stamps}}
        post_state = {STAMP_KEY: {sender: stamp_amount + sender_stamps},
                      SCRATCH_KEY: {sender: sender_balance - stamp_amount}}

        test_interpreter(tx, config_state, post_state)

    def test_stamp_valid_to_balance_all_stamps(self):
        """
        Tests a vaild stamp transaction where the sender converts the entirety of his balance to stamps.
        """
        stamp_amount = 100
        sender_stamps = 200
        sender_balance = 100
        sender, tx = build_stamp_tx(stamp_amount)

        config_state = {BALANCE_KEY: {sender: sender_balance}, STAMP_KEY: {sender: sender_stamps}}
        post_state = {STAMP_KEY: {sender: sender_stamps + stamp_amount},
                      SCRATCH_KEY: {sender: sender_balance - stamp_amount}}

        test_interpreter(tx, config_state, post_state)

    def test_stamp_invalid_insufficient_balance(self):
        """
        Tests an invalid stamp transaction where the sender tries to buy more stamps than he can afford
        """
        stamp_amount = 9999
        sender_stamps = 200
        sender_balance = 100
        sender, tx = build_stamp_tx(stamp_amount)

        config_state = {SCRATCH_KEY: {sender: sender_balance}, STAMP_KEY: {sender: sender_stamps}}

        self.assertRaises(Exception, test_interpreter, tx, config_state, {})

    def test_stamp_invalid_no_balance(self):
        """
        Tests an invalid stamp transaction where the sender has no balance but tries to buy stamps
        """
        stamp_amount = 9999
        sender_stamps = 200
        sender, tx = build_stamp_tx(stamp_amount)

        config_state = {STAMP_KEY: {sender: sender_stamps}}

        self.assertRaises(Exception, test_interpreter, tx, config_state, {})

    def test_stamp_valid_to_stamps(self):
        """
        Tests a valid stamp transaction where the sender tries to convert some of his stamps to balance
        """
        stamp_amount = 256
        sender_stamps = 300
        sender_balance = 10
        sender, tx = build_stamp_tx(-stamp_amount)

        config_state = {BALANCE_KEY: {sender: sender_balance}, STAMP_KEY: {sender: sender_stamps}}
        post_state = {STAMP_KEY: {sender: sender_stamps - stamp_amount},
                      SCRATCH_KEY: {sender: sender_balance + stamp_amount}}

        test_interpreter(tx, config_state, post_state)

    def test_stamp_valid_all_stamps(self):
        """
        Tests a valid stamp transaction where the sender tries to convert all his balance to stamps
        """
        stamp_amount = 256
        sender_stamps = 256
        sender_balance = 100
        sender, tx = build_stamp_tx(-stamp_amount)

        config_state = {SCRATCH_KEY: {sender: sender_balance}, STAMP_KEY: {sender: sender_stamps}}
        post_state = {STAMP_KEY: {sender: sender_stamps - stamp_amount},
                      SCRATCH_KEY: {sender: sender_balance + stamp_amount}}

        test_interpreter(tx, config_state, post_state)

    def test_stamp_invalid_no_stamps(self):
        """
        Tests an invalid stamp transaction where the sender tries to convert some stamps to balance, but he has
        no stamps
        """
        stamp_amount = 256
        sender_balance = 100
        sender, tx = build_stamp_tx(-stamp_amount)

        config_state = {SCRATCH_KEY: {sender: sender_balance}}

        self.assertRaises(Exception, test_interpreter, tx, config_state, {})

    def test_stamp_invalid_insufficient_stamps(self):
        """
        Tests an invalid stamp transaction where the sender tries to convert more stamps than he owns to balance
        """
        stamp_amount = 256
        sender_balance = 100
        sender_stamps = 10
        sender, tx = build_stamp_tx(-stamp_amount)

        config_state = {SCRATCH_KEY: {sender: sender_balance}, STAMP_KEY: {sender: sender_stamps}}

        self.assertRaises(Exception, test_interpreter, tx, config_state, {})

    def test_swap_valid_balance(self):
        """
        Tests a valid swap transaction where the sender has enough funds in balance but scratch is empty
        """
        amount = 100
        sender_balance = 200
        unix_expir = '1000'
        sender, receiver, hash_lock, tx = build_swap_tx(amount, unix_expir)
        t = (sender, receiver, amount, unix_expir)

        config_state = {BALANCE_KEY: {sender: sender_balance}}
        post_state = {SWAP_KEY: {hash_lock: t}, SCRATCH_KEY: {sender: sender_balance - amount}}

        test_interpreter(tx, config_state, post_state)

    def test_swap_valid_balance_all(self):
        """
        Tests a valid swap transaction where the sender tries to send the entirety of his funds
        """
        amount = 200
        sender_balance = 200
        unix_expir = '1000'
        sender, receiver, hash_lock, tx = build_swap_tx(amount, unix_expir)
        t = (sender, receiver, amount, unix_expir)

        config_state = {BALANCE_KEY: {sender: sender_balance}}
        post_state = {SWAP_KEY: {hash_lock: t}, SCRATCH_KEY: {sender: sender_balance - amount}}

        test_interpreter(tx, config_state, post_state)

    def test_swap_invalid_insufficient_balance(self):
        """
        Tests an invalid swap transaction where the sender does not have enough balance in scratch, but enough balance
        in main
        """
        amount = 100
        sender_balance = 200
        sender_scratch = 10
        unix_expir = '1000'
        sender, receiver, hash_lock, tx = build_swap_tx(amount, unix_expir)

        config_state = {SCRATCH_KEY: {sender: sender_scratch}, BALANCE_KEY: {sender: sender_balance}}

        self.assertRaises(Exception, test_interpreter, tx, config_state, {})

    def test_swap_invalid_already_exists(self):
        """
        Tests an invalid swap transaction where the hash lock already exists
        """
        amount = 100
        sender_balance = 200
        unix_expir = '1000'
        sender, receiver, hash_lock, tx = build_swap_tx(amount, unix_expir)
        t = (sender, receiver, amount, unix_expir)

        config_state = {BALANCE_KEY: {sender: sender_balance}, SWAP_KEY: {hash_lock: t}}

        self.assertRaises(Exception, test_interpreter, tx, config_state, {})

    def test_redeem_valid_in_balance(self):
        """
        Tests a valid redeem transaction, where both the sender and receiver exist in balance but not in scratch
        """
        sender_s, sender = ED25519Wallet.new()
        receiver_s, receiver = ED25519Wallet.new()
        amount = 100
        sender_balance = 200
        receiver_balance = 500
        unix_expir = '133700'
        secret = secrets.token_hex(16)
        hash_lock = hash_ripe(secret)
        t = (sender, receiver, amount, unix_expir)

        tx = TestNetTransaction(ED25519Wallet, SHA3POW)
        tx.build(TestNetTransaction.redeem_tx(receiver, secret), receiver_s)

        config_state = {BALANCE_KEY: {sender: sender_balance, receiver: receiver_balance}, SWAP_KEY: {hash_lock: t}}
        post_state = {SCRATCH_KEY: {receiver: receiver_balance + amount},
                      SWAP_KEY: {hash_lock: REMOVED_HASH_ID}}

        test_interpreter(tx, config_state, post_state)

    def test_redeem_valid_in_scratch(self):
        """
        Tests a valid redeem transaction, where both the sender and receiver exist in the scratch
        """
        sender_s, sender = ED25519Wallet.new()
        receiver_s, receiver = ED25519Wallet.new()
        amount = 100
        sender_balance = 200
        receiver_balance = 500
        unix_expir = '133700'
        secret = secrets.token_hex(16)
        hash_lock = hash_ripe(secret)
        t = (sender, receiver, amount, unix_expir)

        tx = TestNetTransaction(ED25519Wallet, SHA3POW)
        tx.build(TestNetTransaction.redeem_tx(receiver, secret), receiver_s)

        config_state = {SCRATCH_KEY: {sender: sender_balance, receiver: receiver_balance}, SWAP_KEY: {hash_lock: t}}
        post_state = {SCRATCH_KEY: {receiver: receiver_balance + amount},
                      SWAP_KEY: {hash_lock: REMOVED_HASH_ID}}

        test_interpreter(tx, config_state, post_state)

    def test_redeem_invalid_wrong_secret(self):
        """
        Tests an invalid redeem transaction where the receiver has the wrong secret
        """
        sender_s, sender = ED25519Wallet.new()
        receiver_s, receiver = ED25519Wallet.new()
        amount = 100
        sender_balance = 200
        receiver_balance = 500
        unix_expir = '133700'
        secret = secrets.token_hex(16)
        different_secret = secrets.token_hex(16)
        hash_lock = hash_ripe(secret)
        t = (sender, receiver, amount, unix_expir)

        tx = TestNetTransaction(ED25519Wallet, SHA3POW)
        tx.build(TestNetTransaction.redeem_tx(receiver, different_secret), receiver_s)

        config_state = {SCRATCH_KEY: {sender: sender_balance, receiver: receiver_balance}, SWAP_KEY: {hash_lock: t}}

        self.assertRaises(Exception, test_interpreter, tx, config_state, {})

    def test_redeem_invalid_tx_sender(self):
        """
        Tests an invalid redeem transaction where the transaction originates from an actor who is neither the original
        recipient nor the original sender
        """
        sender_s, sender = ED25519Wallet.new()
        receiver_s, receiver = ED25519Wallet.new()
        bad_actor_s, bad_actor = ED25519Wallet.new()
        amount = 100
        sender_balance = 200
        receiver_balance = 500
        unix_expir = '133700'
        secret = secrets.token_hex(16)
        hash_lock = hash_ripe(secret)
        t = (sender, receiver, amount, unix_expir)

        tx = TestNetTransaction(ED25519Wallet, SHA3POW)
        tx.build(TestNetTransaction.redeem_tx(bad_actor, secret), bad_actor_s)

        config_state = {SCRATCH_KEY: {sender: sender_balance, receiver: receiver_balance}, SWAP_KEY: {hash_lock: t}}

        self.assertRaises(Exception, test_interpreter, tx, config_state, {})

    def test_redeem_valid_refund_time_expired(self):
        """
        Tests a redeem transaction where the original sender tries to refund the swap after the expiration date
        """
        # TODO -- implement once we have timestamps in the transactions
        return

    def test_redeem_invalid_refund_time_not_expired(self):
        """
        Tests an invalid redeem transaction where the original sender tries to refund the swap before the
        expiration date
        """
        # TODO -- implement once we have timestamps in the transactions
        return

    def test_swap_and_redeem_valid(self):
        """
        Tests a valid swap, and then redeem transaction
        """
        sender_s, sender = ED25519Wallet.new()
        receiver_s, receiver = ED25519Wallet.new()
        amount = 100
        sender_balance = 200
        receiver_balance = 400
        unix_expir = '1000'
        secret = secrets.token_hex(16)
        hash_lock = hash_ripe(secret)

        swap_tx = TestNetTransaction(ED25519Wallet, SHA3POW)
        swap_tx.build(TestNetTransaction.swap_tx(sender, receiver, str(amount), hash_lock, unix_expir), sender_s)
        t = (sender, receiver, amount, unix_expir)

        redeem_tx = TestNetTransaction(ED25519Wallet, SHA3POW)
        redeem_tx.build(TestNetTransaction.redeem_tx(receiver, secret), receiver_s)

        config_state = {BALANCE_KEY: {sender: sender_balance}}
        post_swap_state = {SWAP_KEY: {hash_lock: t}, SCRATCH_KEY: {sender: sender_balance - amount}}
        pre_redeem_state = {SWAP_KEY: {hash_lock: t}, SCRATCH_KEY: {receiver: receiver_balance}}
        post_redeem_state = {SWAP_KEY: {hash_lock: REMOVED_HASH_ID}, SCRATCH_KEY: {receiver: receiver_balance + amount}}

        test_interpreter(swap_tx, config_state, post_swap_state)
        test_interpreter(redeem_tx, pre_redeem_state, post_redeem_state)
