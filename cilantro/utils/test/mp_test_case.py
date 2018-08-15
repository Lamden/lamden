import asyncio, time, cilantro, os, shutil, signal, sys
import zmq.asyncio
from vmnet.launch import launch
from vmnet.webserver import start_ui
from vmnet.testcase import BaseNetworkTestCase
from cilantro.logger import get_logger
from .mp_test import SIG_ABORT, SIG_FAIL, SIG_RDY, SIG_SUCC, SIG_START
from os.path import dirname, join
from functools import wraps

# URL of orchestration node. TODO -- set this to env vars
URL = "tcp://127.0.0.1:5020"

TEST_TIMEOUT = 5
TESTER_POLL_FREQ = 0.1

CILANTRO_PATH = dirname(dirname(cilantro.__path__[0]))

def signal_handler(sig, frame):
    print("Killing docker containers...")
    os.system("docker kill $(docker ps -q)")
    print("Docker containers be ded")
    sys.exit(0)

def vmnet_test(*args, **kwargs):
    def _vmnet_test(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            self = args[0]
            assert isinstance(self, BaseNetworkTestCase), \
                "@vmnet_test can only be used to decorate BaseNetworkTestCase subclass methods (got self={}, but expected " \
                "a BaseNetworkTestCase subclass instance)".format(self)

            klass = self.__class__
            # parent_klass = self.__class__.__bases__[0]  # In Cilantro, this should be MPTestCase
            #
            # # Horrible hack to get MPTestCase to work
            # if parent_klass is not BaseNetworkTestCase:
            #     klass = parent_klass

            # klass.start_docker(run_webui=run_webui)
            # cls = BaseNetworkTestCase
            klass.test_name = klass.__name__
            klass._set_configs(launch(klass.config_file, klass.test_name))

            # Create log directory for test name
            log_dir = join(klass.project_path, 'logs', klass.test_name)
            os.makedirs(log_dir, exist_ok=True)

            if run_webui:
                klass.webserver_proc, klass.websocket_proc = start_ui(
                    klass.test_name, klass.project_path)

            BaseNetworkTestCase.vmnet_test_active = True
            res = func(*args, **kwargs)
            BaseNetworkTestCase.vmnet_test_active = False
            # klass._reset_containers()

            return res

        return wrapper

    if len(args) == 1 and callable(args[0]):
        run_webui = False
        return _vmnet_test(args[0])
    else:
        run_webui = kwargs.get('run_webui', False)
        return _vmnet_test

class MPTestCase(BaseNetworkTestCase):
    config_file = '{}/cilantro/tests/vmnet/configs/cilantro-nodes.json'.format(CILANTRO_PATH)
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
        start_msg += '\n{} STARTING\n'.format(self.id()) + '#' * 80 + '\n' + '#' * 80
        self.log.debug(start_msg)

    def tearDown(self):
        super().tearDown()

        MPTestCase.testers.clear()
        MPTestCase.curr_tester_index = 1

        # if MPTestCase.vmnet_test_active:
        #     self.log.important3("ayyyy im clearing the containers good sir")
        #     self._reset_containers()
        # else:
        #     self.log.fatal("VMNET TEST NOT ACTIVE! NOT CLEARING ANYTHING!")

        # MPTestCase.vmnet_test_active = False

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
            self.log.debug("\n\n{0}\n\n{2} SUCCEEDED WITH {1} SECONDS LEFT\n\n{0}\n"
                           .format('$' * 120, round(timeout, 2), self.id()))
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


# TODO find him a better home
# if hasattr(MPTestCase, 'vmnet_test_active'):
#     if BaseNetworkTestCase.vmnet_test_active:
#         signal.signal(signal.SIGINT, signal_handler)
