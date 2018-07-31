from unittest import TestCase
from cilantro.messages.reactor.reactor_command import ReactorCommand
from cilantro.messages.transaction.standard import StandardTransactionBuilder
from cilantro.messages.envelope.envelope import Envelope
from cilantro.protocol.wallet import Wallet


class TestReactorCommand(TestCase):

    def test_create_with_kwargs(self):
        """
        Tests creating a message without an envelope produces an objects with the expected kwargs
        """
        kwargs = {'callback': 'do_something', 'some_num': '10', 'some_id': '0x5544ddeeff'}

        cmd = ReactorCommand.create(**kwargs)

        self.assertEqual(cmd.kwargs, kwargs)

    def test_create_cmd(self):
        """
        Tests create_cmd
        """
        class_name = 'TestClass'
        func_name = 'do_something_lit'

        kwargs = {'cats': '18', 'dogs': 'over 9000'}

        cmd = ReactorCommand.create_cmd(class_name, func_name, **kwargs)

        self.assertEquals(cmd.func_name, func_name)
        self.assertEqual(cmd.class_name, class_name)
        for k in kwargs:
            self.assertEqual(cmd.kwargs[k], kwargs[k])

        self.assertEqual(cmd.envelope, None)

    def test_create_callback(self):
        """
        Tests create_callback
        """
        callback = 'route'
        kwargs = {'cats': '18', 'dogs': 'over 9000'}

        cmd = ReactorCommand.create_callback(callback, **kwargs)

        self.assertEqual(cmd.callback, callback)
        for k in kwargs:
            self.assertEqual(cmd.kwargs[k], kwargs[k])

    def test_create_with_envelope(self):
        """
        Tests creating a message with an envelope produces an object with the expected properties
        """
        sk, vk = Wallet.new()
        tx = StandardTransactionBuilder.random_tx()
        sender = 'me'
        env = Envelope.create_from_message(message=tx, signing_key=sk)

        cmd = ReactorCommand.create_cmd('some_cls', 'some_func', envelope=env)

        self.assertTrue(ReactorCommand.envelope, env)

    # TODO -- test create_cmd without func_name and class_name throws err

    # TODO -- tests create_callback without callback throws err
