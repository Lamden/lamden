from cilantro.utils.test import MPTesterBase, MPTestCase, mp_testable
from unittest.mock import patch, call, MagicMock
from cilantro.protocol.transport import Router, Composer
from cilantro.protocol.reactor import ReactorInterface
from cilantro.messages import *
from cilantro.protocol.wallets import ED25519Wallet
from cilantro.protocol.statemachine import StateMachine
import asyncio


def random_envelope():
    sk, vk = ED25519Wallet.new()
    tx = StandardTransactionBuilder.random_tx()
    sender = 'me'
    return Envelope.create_from_message(message=tx, signing_key=sk, sender_id=sender)


# TODO -- support multiple classes mp_testable? or is this sketch
@mp_testable(Router)
class MPRouterInterface(MPTesterBase):
    @classmethod
    def build_obj(cls) -> tuple:
        mock_sm = MagicMock(spec=StateMachine)
        router = Router(mock_sm)

        # ReactorInterface.



# TODO -- move this to a test util module or something
@mp_testable(ReactorInterface)
class MPReactorInterface(MPTesterBase):
    @classmethod
    def build_obj(cls) -> tuple:
        mock_parent = MagicMock()
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        reactor = ReactorInterface(mock_parent, loop=loop)

        return reactor, loop




class TransportIntegrationTest(MPTestCase):
