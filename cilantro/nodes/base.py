from cilantro.logger import get_logger
from cilantro.protocol.overlay.auth import Auth
from cilantro.constants.system_config import MAX_BOOT_WAIT
from cilantro.protocol.multiprocessing.worker import Worker
from cilantro.protocol.overlay.daemon import OverlayServer
from cilantro.utils.lprocess import LProcess
from cilantro.storage.vkbook import VKBook

import asyncio
import os
import time
from cilantro.protocol import wallet


class NodeTypes:
    MN = 'mn'
    WITNESS = 'w'
    DELEGATE = 'd'

    _ALL_TYPES = {MN, WITNESS, DELEGATE}

    @classmethod
    def check_vk_in_group(cls, vk: str, group: str):
        assert group in cls._ALL_TYPES, "Group '{}' not a valid node type. Must be in {}".format(group, cls._ALL_TYPES)
        if group == cls.MN:
            return vk in VKBook.get_masternodes()
        if group == cls.WITNESS:
            return vk in VKBook.get_witnesses()
        if group == cls.DELEGATE:
            return vk in VKBook.get_delegates()


# How often (in seconds) a node should ping others to check if they are online
PING_RETRY = min(15, len(VKBook.get_all()))


class NodeBase(Worker):

    # These constants can be overwritten by subclasses
    # For dev, we require all nodes to be online. IRL this could perhaps be 2/3 node for each role  --davis
    REQ_MNS = len(VKBook.get_masternodes())
    REQ_DELS = len(VKBook.get_delegates())
    REQ_WITS = len(VKBook.get_witnesses())

    def __init__(self, ip, signing_key, loop=None, name='Node'):
        # TODO oh lord plz no this
        self.REQ_MNS = len(VKBook.get_masternodes())
        self.REQ_DELS = len(VKBook.get_delegates())
        self.REQ_WITS = len(VKBook.get_witnesses())

        self.log = get_logger(name)
        self.ip = ip
        self.name = name
        self.log.important(self.REQ_MNS)

        self.loop = loop or asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

        Auth.setup(sk_hex=signing_key, reset_auth_folder=True)

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

        self._wait_for_nodes()

        self.start()

    def start(self):
        pass

    def _node_offline_event(self, event: dict):
        self.log.spam("Node with vk {} is still offline.".format(event['vk']))

    def _node_online_event(self, event: dict):
        self.log.debugv("Node with vk {} is online with ip {}!".format(event['vk'], event['ip']))
        self._add_online_vk(event['vk'])

    def _wait_for_nodes(self):
        assert not self.loop.is_running(), "Event loop should not be running when _wait_for_nodes is called!"
        start = time.time()
        self.log.info("Waiting for necessary nodes to boot...")
        self.loop.run_until_complete(self._wait_for_network_rdy())
        self.log.success("Done waiting for necessary nodes to boot! Time spent waiting: {}s".format(time.time()-start))

    async def _wait_for_network_rdy(self):
        elapsed = 0

        # @raghu arnt we are going to sleep for 10 second all the time? proof:
        # max(10, min(2, len(missing_nodes)) ) = max(10, at most 2) = 10
        #
        # num_nodes = min(2, len(self._get_missing_nodes()))
        # time.sleep(max(10, num_nodes))

        # did you mean max(2, len(missing_nodes) ??
        num_nodes = max(2, len(self._get_missing_nodes()))
        time.sleep(max(10, num_nodes))

        while not self._quorum_reached() and elapsed < MAX_BOOT_WAIT:
            # Get missing node set, and try and ping them all (no auth)
            missing_vks = self._get_missing_nodes()
            self.log.spam("Querying status of nodes with vks: {}".format(missing_vks))
            for vk in missing_vks:
                self.manager.overlay_client.check_node_status(vk)
                await asyncio.sleep(0.1)  # sleep to try not flood overlay server with too many requests

            await asyncio.sleep(PING_RETRY)
            elapsed += PING_RETRY

        if elapsed > MAX_BOOT_WAIT:
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
