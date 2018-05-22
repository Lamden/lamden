from cilantro.protocol.transport import Composer


class SuperComposer(Composer):

    def send_transaction(self, sender, receiver, amount):
        pass

    def send_block_contender(self, url, bc):
        pass

    