'''
    Witness

    Witnesses exist primarily to check the validity of proofs of transactions sent out by masternodes.
    They subscribe to masternodes on the network, confirm the hashcash style proof provided by the sender is valid, and
    then go ahead and pass the transaction along to delegates to include in a block. They will also facilitate
    transactions that include stake reserves being spent by users staking on the network.
'''
from cilantro import Constants
from cilantro.nodes import NodeBase
from cilantro.protocol.statemachine import State, receive
from cilantro.messages import StandardTransaction, Envelope


class WitnessBaseState(State):
    def enter(self, prev_state): pass

    def exit(self, next_state): pass

    def run(self): pass

    @receive(StandardTransaction)
    def recv_tx(self, tx: StandardTransaction):
        self.log.critical("Witness not configured to recv tx: {}".format(tx))


class WitnessBootState(WitnessBaseState):
    def enter(self, prev_state):
        self.parent.reactor.add_sub(url=Constants.Testnet.Masternode.InternalUrl)
        self.parent.reactor.add_pub(url=self.parent.url)

    def run(self):
        self.parent.transition(WitnessRunState)

    def exit(self, next_state):
        self.parent.reactor.notify_ready()


class WitnessRunState(WitnessBaseState):
    @receive(StandardTransaction)
    def recv_tx(self, tx: StandardTransaction):
        self.log.critical("run state got tx: {}".format(tx))
        env = Envelope.create(tx)
        self.parent.reactor.pub(url=self.parent.url, data=env.serialize())


class Witness(NodeBase):
    _INIT_STATE = WitnessBootState
    _STATES = [WitnessBootState, WitnessRunState]

    def __init__(self, url=None, signing_key=None, slot=0):
        if url is None and signing_key is None:
            node_info = Constants.Testnet.Witnesses[slot]
            url = node_info['url']
            signing_key = node_info['sk']
        super().__init__(url=url, signing_key=signing_key)
        self.log.info("Witness being created on slot {} with url {}".format(slot, url))
