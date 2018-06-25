import asyncio
import zmq.asyncio

import time
import os
import shutil
import sys
import dill

from unittest import TestCase
from cilantro.logger import get_logger
from cilantro.utils.test.mp_test import MPTesterBase, SIG_ABORT, SIG_FAIL, SIG_RDY, SIG_SUCC, SIG_START
from .god import God

# URL of orchestration node. TODO -- set this to env vars
URL = "tcp://127.0.0.1:5020"

TEST_TIMEOUT = 5
TESTER_POLL_FREQ = 0.1


class MPTestCase(TestCase):
    testname = 'base_test'
    project = 'cilantro'
    compose_file = 'cilantro-nodes.yml'

    def run_script(self, params):
        """
            Runs launch.py to start-up or tear-down for network of nodes in the
            specifed Docker network.
        """
        launch_path = '/Users/davishaba/Developer/Lamden/vmnet/docker/launch.py'
        os.system('python {} --project {} {}'.format(
            launch_path,
            self.project,
            params
        ))

    def execute_python(self, node, fn, async=True, python_version='3.6'):
        fn_str = dill.dumps(fn, 0)
        exc_str = 'docker exec {} /usr/bin/python{} -c \"import dill; fn = dill.loads({}); fn();\" {}'.format(
            node,
            python_version,
            fn_str,
            '&' if async else ''
        )
        os.system(exc_str)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.log = get_logger("MPTestOrchestrater")
        self.project = 'cilantro'

    def setUp(self):
        super().setUp()
        assert len(God.testers) == 0, "setUp called but God._testers is not empty ({})" \
            .format(God.testers)

        # God.node_map = self.nodemap  # TODO fix and implement

        start_msg = '\n' + '#' * 80 + '\n' + '#' * 80
        start_msg += '\n\t\t\t TEST STARTING\n' + '#' * 80 + '\n' + '#' * 80
        self.log.debug(start_msg)

    def tearDown(self):
        super().tearDown()
        God.testers.clear()
        God.node_map = None

    def start(self, timeout=TEST_TIMEOUT):
        """
        Start the test orchestrator, which polls tester objects living on seperate process/machines for assertions.

        We organize all registered testers into 'active' testers, which are passed in an assertions function,
        and 'passive' testers which do not make assertions but still interact with other testers.
        Testers' output queues are polled  every TEST_POLL_FREQ seconds for maximum of TEST_TIMEOUT seconds,
        waiting for them to finish (if ever). When an 'active' testers passes its assertions, we move it to
        'passives'. When all active testers are finished, we send SIG_ABORTs to all testers to clean them up
        """
        # self.log.critical("\nSTARTING TEST WITH TESTERS {}\n".format(God.testers))
        assert len(God.testers) > 0, "start() called, but list of testers empty (MPTesterBase._testers={})"\
                                         .format(God.testers)

        actives, passives, fails, timeout = self._poll_testers(timeout)

        self.log.debug("Cleaning up tester processes")
        for t in actives + passives + fails:
            t.socket.send_pyobj(SIG_ABORT)
            t.teardown()

        # If there are no active testers left and none of them failed, we win
        if len(actives) + len(fails) == 0:
            self.log.debug("\n\n{0}\n\n\t\t\tTESTERS SUCCEEDED WITH {1} SECONDS LEFT\n\n{0}\n"
                              .format('$' * 120, timeout))
        else:
            fail_msg = "\n\n\nfail_msg:\n{0}\nASSERTIONS TIMED OUT FOR TESTERS: \n\n\n".format('-' * 120)
            for t in fails + actives:
                fail_msg += "{}\n".format(t)
            fail_msg += "{0}\n".format('-' * 120)
            self.log.error(fail_msg)
            raise Exception()

    def _poll_testers(self, timeout) -> tuple:
        start_msg = '\n' + '~' * 80
        start_msg += '\n Polling testers procs every {} seconds, with test timeout of {} seconds\n'\
            .format(TESTER_POLL_FREQ, timeout)
        start_msg += '~' * 80
        self.log.debug(start_msg)

        actives = [t for t in God.testers if t.assert_fn]
        passives = [t for t in God.testers if not t.assert_fn]
        fails = []

        # Start the assertion on the active tester procs
        for t in actives:
            t.socket.send_pyobj(SIG_START)

        # Poll testers for a max of 'timeout' seconds
        while timeout > 0:
            for t in actives:
                try:
                    msg = t.socket.recv(flags=zmq.NOBLOCK)
                    self.log.debug("\nGOT MSG {} FROM TESTER <{}>\n".format(msg, t))

                    # 'ignore' SIG_RDY
                    if msg == SIG_RDY:
                        continue

                    actives.remove(t)

                    if msg == SIG_SUCC:
                        passives.append(t)
                    else:
                        fails.append(t)
                except Exception as e:
                    pass

            # Break if all active testers have finished
            if len(actives) == 0:
                self.log.debug("Breaking from loop, no active tester left")
                break

            # Sleep for TEST_POLL_FREQ seconds
            timeout -= TESTER_POLL_FREQ
            time.sleep(TESTER_POLL_FREQ)

        return actives, passives, fails, timeout
