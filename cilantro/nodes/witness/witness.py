from cilantro import Constants
from cilantro.nodes.base import Node
from cilantro.models import StandardTransaction, Message
from cilantro.protocol.statemachine import StateMachine, State
from cilantro.logger.base import get_logger

'''
    Witness

    Witnesses exist primarily to check the validity of proofs of transactions sent out by masternodes.
    They subscribe to masternodes on the network, confirm the hashcash style proof provided by the sender is valid, and
    then go ahead and pass the transaction along to delegates to include in a block. They will also facilitate
    transactions that include stake reserves being spent by users staking on the network.
'''

Proof = Constants.Protocol.Proofs


class Witness(Node, StateMachine):
    def __init__(self, sub_port=Constants.Witness.SubPort, pub_port=Constants.Witness.PubPort):
        Node.__init__(self,
                      sub_port=sub_port,
                      pub_port=pub_port)

        self.hasher = Proof
        self.log = get_logger('witness')
        self.log.info('Witness has appeared.')

        STATES = [WitnessBootState, WitnessLiveState]
        StateMachine.__init__(self, WitnessBootState, STATES)

    def zmq_callback(self, msg):
        # assume standard tx
        self.log.info('Got a message: {}'.format(msg))
        try:
            msg = Message.from_bytes(msg)
            self.log.info("Witness unpacked msg: {}".format(msg))
            self.log.info("Witness unpacked msg data: {}".format(msg._data))

            # tx = StandardTransaction.from_bytes(msg)
            if msg.type == 0:


            elif msg.type == 1:


            # self.logger.info(tx._data)
            # self.pub_socket.send(tx.serialize())
        except Exception as e:
            self.log.info('Witness could not deserialize msg with error: {}'.format(e))

    def pipe_callback(self, msg):
        pass


class WitnessBootState(State):
    name = "WitnessBootState"

    def __init__(self, state_machine=None):
        super().__init__(state_machine)
        self.log = get_logger("Witness.BootState")

    def handle_message(self, msg):
        self.log.info("!!! IN BOOT !!! got msg: {}".format(msg))

    def enter(self, prev_state):
        self.log.info("Witness is booting...")

    def exit(self, next_state):
        self.log.info("Witness exiting boot procedure...")

    def run(self):
        self.sm.transition(WitnessLiveState)


class WitnessLiveState(State):
    name = "WitnessLiveState"

    def __init__(self, state_machine=None):
        super().__init__(state_machine)
        self.log = get_logger("Witness.LiveState")

    def handle_message(self, msg):
        self.log.info("got msg: {}".format(msg))
        # TODO -- application logic for routing goes here

    def enter(self, prev_state):
        self.log.info("Witness entering live state...")

    def exit(self, next_state):
        self.log.info("Witness exiting live state...")

    def run(self):
        self.log.info("Witness live state is running.")