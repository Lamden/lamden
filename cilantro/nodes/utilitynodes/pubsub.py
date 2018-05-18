from cilantro.logger import get_logger
from cilantro.nodes.utilitynodes import BaseNode
from cilantro.messages import *
from cilantro.protocol.wallets import ED25519Wallet
from cilantro.protocol.networks import *
import asyncio, os, warnings

log = get_logger(__name__)
log.debug("-- MAIN THREAD ({}) --".format(os.getenv('HOST_IP', '127.0.0.1')))

def random_envelope():
    sk, vk = ED25519Wallet.new()
    tx = StandardTransactionBuilder.random_tx()
    return Envelope.create_from_message(message=tx, signing_key=sk, verifying_key=vk)

class PubNode(BaseNode, Grouping):
    def __init__(self):
        super().__init__()
        super(BaseNode, self).__init__()
        super(Grouping, self).__init__()

    async def debug_forever_pub(self):
        while True:
            env = random_envelope()
            log.debug('sending {}'.format(env))
            self.designate_next_group()
            self.composer.send_pub_env(envelope=env, filter='')
            await asyncio.sleep(1)

class SubNode(BaseNode, Grouping):
    def __init__(self, pub_ip):
        super(SubNode, self).__init__()

if __name__ == "__main__":
    publisher = PubNode()
    # nodes = [SubNode() for i in range(8)]
