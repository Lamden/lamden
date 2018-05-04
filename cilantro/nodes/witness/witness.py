'''
    Witness

    Witnesses exist primarily to check the validity of proofs of transactions sent out by masternodes.
    They subscribe to masternodes on the network, confirm the hashcash style proof provided by the sender is valid, and
    then go ahead and pass the transaction along to delegates to include in a block. They will also facilitate
    transactions that include stake reserves being spent by users staking on the network.
'''
from cilantro import Constants
from cilantro.nodes import NodeBase
from cilantro.protocol.statemachine import State, recv
from cilantro.messages import TransactionBase, Envelope
from cilantro.utils import TestNetURLHelper


class WitnessBaseState(State):
    def enter(self, prev_state): pass

    def exit(self, next_state): pass

    def run(self): pass

    @recv(TransactionBase)
    def recv_tx(self, tx: TransactionBase):
        self.log.critical("Witness not configured to recv tx: {}".format(tx))


class WitnessBootState(WitnessBaseState):
    """Witness boot state has witness sub to masternode and establish a pub socket and router socket"""
    def enter(self, prev_state):
        self.parent.composer.add_pub(url=TestNetURLHelper.pubsub_url(self.parent.url))
        self.parent.composer.add_router(url=TestNetURLHelper.dealroute_url(self.parent.url))

        self.parent.composer.add_sub(url=TestNetURLHelper.pubsub_url(Constants.Testnet.Masternode.InternalUrl),
                                     filter=Constants.Testnet.ZmqFilters.WitnessMasternode)
        self.log.critical("Witness subscribing to URL: {}"
                          .format(TestNetURLHelper.pubsub_url(Constants.Testnet.Masternode.InternalUrl)))

    def run(self):
        self.parent.transition(WitnessRunState)

    def exit(self, next_state):
        pass


class WitnessRunState(WitnessBaseState):
    """Witness run state has the witness receive transactions sent from masternode"""

    # TODO .. solution to 'relay' pub envelopes
    # from MN to a delegate. Hacko is just to create a new envelope
    # (but then UUID will be diff, and so will sig/og sender!) ...
    # thus for relaying messages, if we arent doing anything to it,
    # we may as well pass that mfker along in the ReactorDaemon. Right? ... if we arent doing any checks/processing
    # on it in the SM, why bother piping the data all the way to main
    # thread and then back to daemon, right?
    @recv(TransactionBase)
    def recv_tx(self, tx: TransactionBase):
        self.log.critical("ayyyy witness got tx: {}".format(tx))  # debug line, remove later
        self.parent.composer.send_pub_msg(message=tx, filter=Constants.ZmqFilters.WitnessDelegate)
        self.log.critical("witness published dat tx to the homies")  # debug line, remove later


class Witness(NodeBase):
    _INIT_STATE = WitnessBootState
    _STATES = [WitnessBootState, WitnessRunState]

    def __init__(self, loop, url=None, signing_key=None, slot=0):
        # TODO -- move away from this shitty ass slot logic, and integrate a more proper node list from VMNet
        if url is None and signing_key is None:
            node_info = Constants.Testnet.Witnesses[slot]
            url = node_info['url']
            signing_key = node_info['sk']

        super().__init__(url=url, signing_key=signing_key, loop=loop)
