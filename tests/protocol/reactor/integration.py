
from unittest.mock import MagicMock, call, patch
from cilantro.messages import *
from cilantro.protocol.wallets import ED25519Wallet
from cilantro.protocol.reactor import ReactorInterface
from cilantro.protocol.reactor.core import CHILD_RDY_SIG
from cilantro.protocol.reactor.executor import *
from cilantro.messages import ReactorCommand
from cilantro.utils.test import ThiccTestCase, TTBase, thicc_testable
import time


URL = 'tcp://127.0.0.1:9988'
FILTER = 'TEST_FILTER'


@thicc_testable(ReactorInterface)
class TTReactorInterface(TTBase):
    @classmethod
    def build_obj(cls) -> tuple:
        mock_parent = MagicMock()
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        reactor = ReactorInterface(mock_parent, loop=loop)

        return reactor, loop


class IntegrationTestReactor(ThiccTestCase):
    @classmethod
    def random_envelope(cls):
        sk, vk = ED25519Wallet.new()
        tx = StandardTransactionBuilder.random_tx()
        sender = 'me'
        return Envelope.create_from_message(message=tx, signing_key=sk, sender_id=sender)

    def test_subpub_1(self):
        """
        Tests sub/pub 1-1 with one message
        """
        def configure_interface(reactor: ReactorInterface):
            reactor._run_callback = MagicMock()
            return reactor

        def run_assertions(reactor: ReactorInterface):
            callback = 'route'
            data = env.serialize()
            reactor._run_callback.assert_called_with(callback, data)

        env = IntegrationTestReactor.random_envelope()

        sub = TTReactorInterface(config_fn=configure_interface, assert_fn=run_assertions, name='** SUB')
        pub = TTReactorInterface(name='++ PUB')

        add_sub_cmd = ReactorCommand.create_cmd(SubPubExecutor.__name__, SubPubExecutor.add_sub.__name__, url=URL,
                                                filter=FILTER)
        add_pub_cmd = ReactorCommand.create_cmd(SubPubExecutor.__name__, SubPubExecutor.add_pub.__name__, url=URL)
        send_pub_cmd = ReactorCommand.create_cmd(SubPubExecutor.__name__, SubPubExecutor.send_pub.__name__,
                                                 envelope=env, filter=FILTER)

        sub.send_cmd(add_sub_cmd)
        pub.send_cmd(add_pub_cmd)
        time.sleep(0.2)
        pub.send_cmd(send_pub_cmd)

        self.start()























