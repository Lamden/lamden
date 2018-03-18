from cilantro import Constants
from cilantro.nodes.base import Node, zmq_listener, zmq_sender, Router, BIND, CONNECT
from cilantro.messages import StandardTransaction, Envelope
from cilantro.protocol.statemachine import StateMachine, State
from cilantro.logger.base import get_logger

import zmq
'''
    Witness

    Witnesses exist primarily to check the validity of proofs of transactions sent out by masternodes.
    They subscribe to masternodes on the network, confirm the hashcash style proof provided by the sender is valid, and
    then go ahead and pass the transaction along to delegates to include in a block. They will also facilitate
    transactions that include stake reserves being spent by users staking on the network.
'''


class Witness(StateMachine):
    def __init__(self):
        self.log = get_logger('Witness')
        self.log.debug("Creating witness...")

        self.sub_url = 'tcp://127.0.0.1:{}'.format(Constants.Witness.SubPort)
        self.pub_url = 'tcp://127.0.0.1:{}'.format(Constants.Witness.PubPort)#'ipc://witness'

        self.subscriber_pipe, self.subscriber_process = zmq_listener(socket_type=zmq.SUB,
                                                                     connection_type=CONNECT,
                                                                     url=self.sub_url)
        self.subscriber_process.start()

        self.publisher_pipe, self.publisher_process = zmq_sender(socket_type=zmq.PUB,
                                                                 connection_type=BIND,
                                                                 url=self.pub_url)
        self.publisher_process.start()

        callbacks = [(self.subscriber_pipe, self.handle_message)]
        self.router = Router(callbacks)
        self.router.start()

        self.log.info('Witness has appeared (this is main thread).')

        STATES = [WitnessBootState, WitnessLiveState]
        StateMachine.__init__(self, WitnessBootState, STATES)

    def handle_message(self, msg):
        self.log.info('Got a message: {}'.format(msg))
        try:
            msg = Envelope.from_bytes(msg)
            self.log.info("Witness unpacked msg: {}".format(msg))
            self.log.info("Witness unpacked msg data: {}".format(msg._data))

            # TODO route msg, validate pow

            msg_binary = msg.serialize()
            self.publisher_pipe.send(msg_binary)
            self.log.info("Witness sent msg packet to publisher port: {}, with data {}"
                          .format(self.pub_url, msg_binary))

            # tx = StandardTransaction.from_bytes(msg
            # self.logger.info(tx._data)
            # self.pub_socket.send(tx.serialize())
        except Exception as e:
            self.log.info('Witness could not deserialize msg with error: {}'.format(e))


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