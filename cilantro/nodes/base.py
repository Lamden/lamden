from cilantro.logger import get_logger
from cilantro.constants.system_config import MAX_BOOT_WAIT
from cilantro.protocol.states.statemachine import StateMachine
from cilantro.protocol.multiprocessing.worker import Worker
from cilantro.protocol.overlay.daemon import OverlayServer
from cilantro.utils.lprocess import LProcess
from cilantro.storage.vkbook import VKBook

import asyncio
import os
import time
from cilantro.protocol import wallet

# MANDATORY NAP TIME (How long each node sleeps after starting its overlay server)
# Technically, the system will work without this nap but allowing some padding time for dynamic discovery and such
# limits the number of re-auth attempts and lookup retries
BOOT_DELAY = 5

PING_RETRY = 8  # How often nodes should send


def take_a_nice_relaxing_nap(log):
    log.important("Taking a nice relaxing {} second nap while I wait for everybody to boot".format(BOOT_DELAY))
    time.sleep(BOOT_DELAY)
    log.important("Done with my boot nap. Time to get to get work.")


class NodeBase(StateMachine, Worker):

    def __init__(self, ip, signing_key, loop=None, name='Node'):
        self.log = get_logger(name)

        self.loop = loop or asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

        self.log.notice("Starting overlay service")
        self.overlay_proc = LProcess(target=OverlayServer, kwargs={'sk': signing_key})
        self.overlay_proc.start()

        # TODO remove this once we implement a 'Staging' state for all nodes
        take_a_nice_relaxing_nap(self.log)

        # Init Super Classes (we had to start the Overlay Server first)
        Worker.__init__(self, signing_key=signing_key, loop=loop, name=name)

        StateMachine.__init__(self)

        self.ip = ip
        self.name = name

        self.log.important3("Node with vk {} has ip {}".format(self.verifying_key, ip))

        super().start()  # Start the state machine


class NewNodeBase(Worker):

    # For dev, we require all nodes to be online. IRL this could perhaps be 2/3 node for each role  --davis
    # These constants can be overwritten by subclasses
    REQ_MNS = len(VKBook.get_masternodes())
    REQ_DELS = len(VKBook.get_delegates())
    REQ_WITS = len(VKBook.get_witnesses())

    def __init__(self, ip, signing_key, loop=None, name='Node', start=True):
        self.log = get_logger(name)
        self.ip = ip
        self.name = name

        self.loop = loop or asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

        # Variables to track connected nodes when booting
        self.online_mns, self.online_dels, self.online_wits = set(), set(), set()

        self.log.notice("Starting overlay service")
        self.overlay_proc = LProcess(target=OverlayServer, kwargs={'sk': signing_key})
        self.overlay_proc.start()  # TODO should we make this proc a daemon?

        # NOTE: We do not call super() init first thing b/c we must start the OverlayServer before starting the
        # OverlayClient, which happens in Worker's init
        super().__init__(signing_key=signing_key, loop=loop, name=name)

        self.log.important3("Node with vk {} has ip {}".format(self.verifying_key, ip))
        self.add_overlay_handler_fn('node_offline', self._node_offline_event)
        self.add_overlay_handler_fn('node_online', self._node_online_event)
        if start:
            self._wait_for_nodes()

    def _node_offline_event(self, event: dict):
        assert event['event'] == 'node_offline', "Wrong handler wrong event wtf"  # TODO remove
        self.log.spam("Node with vk {} is still offline.".format(event['vk']))

    def _node_online_event(self, event: dict):
        assert event['event'] == 'node_online', "Wrong handler wrong event wtf"  # TODO remove
        self.log.debugv("Node with vk {} is online with ip {}!".format(event['vk'], event['ip']))
        self._add_online_vk(event['vk'])

    def _wait_for_nodes(self):
        assert not self.loop.is_running(), "Event loop should not be running when _wait_for_nodes is called!"
        start = time.time()
        self.log.notice("Waiting for necessary nodes to boot...")
        self.loop.run_until_complete(self._wait_for_network_rdy())
        self.log.notice("Done waiting for necessary nodes to boot! Time spent waiting: {}s".format(time.time()-start))

    async def _wait_for_network_rdy(self):
        elasped = 0
        while not self._quorum_reached() and elasped < MAX_BOOT_WAIT:
            # Get missing node set, and try and ping them all (no auth)
            missing_vks = self._get_missing_nodes()
            self.log.spam("Querying status of nodes with vks: {}".format(missing_vks))
            for vk in missing_vks:
                self.manager.overlay_client.check_node_status(vk)

            await asyncio.sleep(PING_RETRY)
            elasped += PING_RETRY

        if elasped > MAX_BOOT_WAIT:
            err = "Node could not connect to reach required qourum in timeout of {}s!\nMn set: {}\nDelegate set: {}" \
                  "\nWitness set: {}".format(MAX_BOOT_WAIT, self.online_mns, self.online_dels, self.online_wits)
            self.log.fatal(err)
            raise Exception(err)

    def _get_missing_nodes(self) -> set:
        missing_dels = set(VKBook.get_delegates()) - self.online_dels
        missing_mns = set(VKBook.get_masternodes()) - self.online_mns
        missing_wits = set(VKBook.get_witnesses()) - self.online_wits

        return missing_dels.union(missing_mns).union(missing_wits)

    def _quorum_reached(self) -> bool:
        return (self.REQ_MNS <= len(self.online_mns)) and (self.REQ_DELS <= len(self.online_dels)) and \
               (self.REQ_WITS <= len(self.online_wits))

    def _add_online_vk(self, vk: str):
        # Dev check (maybe dont do this IRL)
        assert vk in VKBook.get_all(), "VK {} not in VKBook vks {}".format(vk, VKBook.get_all())
        self.log.debugv("Adding vk {} to online nodes".format(vk))

        if vk in VKBook.get_witnesses():
            self.online_wits.add(vk)
        if vk in VKBook.get_delegates():
            self.online_dels.add(vk)
        if vk in VKBook.get_masternodes():
            self.online_mns.add(vk)


