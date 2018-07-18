import asyncio
import zmq.asyncio
from vmnet.test.base import *
import time
from cilantro.logger import get_logger
from .mp_test import SIG_ABORT, SIG_FAIL, SIG_RDY, SIG_SUCC, SIG_START
from os.path import dirname
import cilantro

# URL of orchestration node. TODO -- set this to env vars
URL = "tcp://127.0.0.1:5020"

TEST_TIMEOUT = 5
TESTER_POLL_FREQ = 0.1

CILANTRO_PATH = dirname(dirname(cilantro.__path__[0]))


import signal
import sys
import os
def signal_handler(sig, frame):
    print("Killing docker containers...")
    os.system("docker kill $(docker ps -q)")
    print("Docker containers be ded")
    sys.exit(0)
signal.signal(signal.SIGINT, signal_handler)


class MPTestCase(BaseNetworkTestCase):
    compose_file = '{}/cilantro/tests/vmnet/compose_files/cilantro-nodes.yml'.format(CILANTRO_PATH)

    local_path = CILANTRO_PATH
    docker_dir = '{}/cilantro/tests/vmnet/docker_dir'.format(CILANTRO_PATH)
    logdir = '{}/cilantro/logs'.format(CILANTRO_PATH)
    setuptime = 8

    testers = []
    curr_tester_index = 1

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.log = get_logger("MPTestOrchestrater")

    @classmethod
    def next_container(cls) -> tuple:
        """
        Retreives the next available docker image.
        :return: A 2 tuple containing the ip and name of container in the form: (name: str, ip: str)
        """
        num = MPTestCase.curr_tester_index
        name = "node_{}".format(num)

        assert num <= len(cls.nodemap), "Tester object number {} exceeds tester capacity of {}".format(num, len(cls.nodemap))
        assert name in cls.nodemap, "Node named {} not found in node map {}".format(name, cls.nodemap)

        MPTestCase.curr_tester_index += 1

        return name, cls.nodemap[name]

    def setUp(self):
        super().setUp()
        assert len(MPTestCase.testers) == 0, "setUp called but God._testers is not empty ({})" \
            .format(MPTestCase.testers)

        start_msg = '\n' + '#' * 80 + '\n' + '#' * 80
        start_msg += '\n\t\t\t TEST STARTING\n' + '#' * 80 + '\n' + '#' * 80
        self.log.debug(start_msg)

    def tearDown(self):
        super().tearDown()

        MPTestCase.testers.clear()
        MPTestCase.curr_tester_index = 1

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
        assert len(MPTestCase.testers) > 0, "start() called, but list of testers empty (MPTesterBase._testers={})"\
                                            .format(MPTestCase.testers)

        actives, passives, fails, timeout = self._poll_testers(timeout)

        self.log.debug("Cleaning up tester processes")
        for t in actives + passives + fails:
            t.socket.send_pyobj(SIG_ABORT)
            t.teardown()

        # If there are no active testers left and none of them failed, we win
        if len(actives) + len(fails) == 0:
            self.log.debug("\n\n{0}\n\n\t\t\tTESTERS SUCCEEDED WITH {1} SECONDS LEFT\n\n{0}\n"
                           .format('$' * 120, round(timeout, 2)))
        else:
            fail_msg = "\n\nfail_msg:\n{0}\nASSERTIONS TIMED OUT FOR TESTERS: \n\n".format('-' * 120)
            for t in fails + actives:
                fail_msg += "{}\n".format(t)
            fail_msg += "{0}\n".format('-' * 120)
            self.log.error(fail_msg)
            time.sleep(0.2)  # block while this message has time to log correctly
            raise Exception()

    def _poll_testers(self, timeout) -> tuple:
        start_msg = '\n' + '~' * 80
        start_msg += '\nPolling testers procs every {} seconds, with test timeout of {} seconds\n'\
            .format(TESTER_POLL_FREQ, timeout)
        start_msg += '~' * 80
        self.log.debug(start_msg)

        actives = [t for t in MPTestCase.testers if t.assert_fn]
        passives = [t for t in MPTestCase.testers if not t.assert_fn]
        fails = []

        # Start the assertion on the active tester procs
        for t in actives:
            t.socket.send_pyobj(SIG_START)

        # Poll testers for a max of 'timeout' seconds
        while timeout > 0:
            for t in actives:
                try:
                    msg = t.socket.recv(flags=zmq.NOBLOCK)
                    self.log.debug("GOT MSG {} FROM TESTER <{}>".format(msg, t))

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
