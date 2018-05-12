import unittest
import logging


class LogCounter(logging.Filter):
    """Counts the number of WARNING or higher log records."""
    def __init__(self, *args, **kwargs):
        logging.Filter.__init__(self, *args, **kwargs)
        self.info_count = self.warning_count = self.error_count = 0

    def filter(self, record):
        if record.levelno >= logging.ERROR:
            self.error_count += 1
        elif record.levelno >= logging.WARNING:
            self.warning_count += 1
        elif record.levelno >= logging.INFO:
            self.info_count += 1
        return True


TEST_MODULES = [
    'tests.messages.consensus.test_block_contender',
    'tests.messages.consensus.test_block_data',
    'tests.messages.consensus.test_merkle_signature',

    'tests.messages.envelope.test_envelope',
    'tests.messages.envelope.test_message',
    'tests.messages.envelope.test_message_meta',
    'tests.messages.envelope.test_seal',

    'tests.messages.reactor.test_reactor_command',

    'tests.messages.transactions.test_redeemTransaction',
    'tests.messages.transactions.test_standard',
    'tests.messages.transactions.test_swapTransaction',
    'tests.messages.transactions.test_transactionContainer',
    'tests.messages.transactions.test_voteTransaction',

    'tests.protocol.structures.test_envelope_auth',
    'tests.protocol.structures.test_merkleTree'

]


if __name__ == '__main__':
    suite = unittest.TestSuite()
    loader = unittest.TestLoader()
    suite.addTests(loader.loadTestsFromNames(TEST_MODULES))

    runner = unittest.TextTestRunner(verbosity=3)
    result = runner.run(suite)
    print(result.errors)
    print(result.failures)



