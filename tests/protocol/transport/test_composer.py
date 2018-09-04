from unittest import TestCase
from unittest.mock import MagicMock
from cilantro.protocol.transport import Composer
from cilantro.protocol.executors import ReactorInterface
from cilantro.protocol import wallet

W = wallet
TESTER_RETURN_VAL = b'yo'

# class TestComposer(TestCase):
#
#     def test_init(self):
#         """
#         Tests init creates an object with the expected properties
#         """
#         sk, vk = W.new()
#         interface = MagicMock(spec=ReactorInterface)
#         sender_id = 'yuh_boi'
#
#         comp = Composer(interface=interface, signing_key=sk)
#
#         self.assertEqual(comp.interface, interface)
#         # self.assertEqual(comp.sender_id, sender_id)
#         self.assertEqual(comp.signing_key, sk)
#         self.assertEqual(comp.verifying_key, vk)

    # TODO test _package_msg

    # TODO tests that each function creates the expected command and passes it to send_cmd

    # def test_package_data_envelope(self):
    #     """
    #     Tests that _package_data returns the unaltered envelope if an Envelope type is passed in
    #     """
    #     sk, vk = W.new()
    #     interface = MagicMock(spec=ReactorInterface)
    #     sender_id = 'yuh_boi'
    #     mock_env = MagicMock(spec=Envelope)
    #
    #     comp = Composer(interface=interface, signing_key=sk, sender_id=sender_id)
    #     output = comp._package_data(mock_env)
    #
    #     self.assertEqual(output, mock_env)
    #
    # # @patch("cilantro.protocol.transport.composer.Envelope")
    # @patch.object(Envelope, "create_from_message",)
    # # @patch.object("cilantro.messages.envelope.envelope.Envelope", "create_from_message")
    # def test_package_data_message(self, mock_method):
    #     """
    #     Tests _package_data with a MessageBase subclass. This should involve Envelope.create_from_message....
    #     """
    #     print("test scope got mock env: {}".format(mock_method))
    #
    #     sk, vk = W.new()
    #     interface = MagicMock(spec=ReactorInterface)
    #     sender_id = 'yuh_boi'
    #     env = Envelope()
    #
    #     return_data = b'hi'
    #     # mock_env_class.create_from_message.return_value = return_data
    #     mock_method.return_value = return_data
    #
    #     comp = Composer(interface=interface, signing_key=sk, sender_id=sender_id)
    #     output = comp._package_data(env)
    #
    #     # mock_env_class.create_from_message.assert_called()
    #     self.assertEqual(output, return_data)
