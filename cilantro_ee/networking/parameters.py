from cilantro_ee.constants.ports import DHT_PORT, EVENT_PORT, DISCOVERY_PORT, BLOCK_SERVER, MN_PUB_PORT, \
    DELEGATE_PUB_PORT
from cilantro_ee.sockets import services
from cilantro_ee.storage import VKBook
from cilantro_ee.sockets.services import get

import json
import zmq.asyncio
import asyncio


class ServiceType:
    PEER = 0
    EVENT = 1
    DISCOVERY = 2
    BLOCK_SERVER = 3
    SUBBLOCK_BUILDER_PUBLISHER = 4
    BLOCK_AGGREGATOR = 5
    TX_BATCH_INFORMER = 6
    BLOCK_NOTIFICATIONS = 7
    TX_BATCHER = 8
    BLOCK_AGGREGATOR_CONTROLLER = 9
    INCOMING_WORK = 10


class NetworkParameters:
    def __init__(self,
                 peer_port=DHT_PORT, peer_ipc='peers',
                 event_port=EVENT_PORT, event_ipc='events',
                 discovery_port=DISCOVERY_PORT, discovery_ipc='discovery',
                 block_port=BLOCK_SERVER, block_ipc='blocks',
                 sbb_pub_port=MN_PUB_PORT, sbb_pub_ipc='sbb_publisher',
                 block_agg_port=DELEGATE_PUB_PORT, block_agg_ipc='block_aggregator',
                 tx_batch_informer_port=9999, tx_batch_informer_ipc='tx_batch_informer',
                 block_notifications_port=9998, block_notifications_ipc='block_notifications',
                 tx_batcher_port=9997, tx_batcher_ipc='tx_batcher',
                 block_agg_controller_port=9996, block_agg_controller_ipc='block_agg_controller',
                 incoming_work_port=9995, incoming_work_ipc='incoming_work'
                 ):

        self.params = {
            ServiceType.PEER: (peer_port, peer_ipc),
            ServiceType.EVENT: (event_port, event_ipc),
            ServiceType.DISCOVERY: (discovery_port, discovery_ipc),
            ServiceType.BLOCK_SERVER: (block_port, block_ipc),
            ServiceType.SUBBLOCK_BUILDER_PUBLISHER: (sbb_pub_port, sbb_pub_ipc),
            ServiceType.BLOCK_AGGREGATOR: (block_agg_port, block_agg_ipc),
            ServiceType.TX_BATCH_INFORMER: (tx_batch_informer_port, tx_batch_informer_ipc),
            ServiceType.BLOCK_NOTIFICATIONS: (block_notifications_port, block_notifications_ipc),
            ServiceType.TX_BATCHER: (tx_batcher_port, tx_batcher_ipc),
            ServiceType.BLOCK_AGGREGATOR_CONTROLLER: (block_agg_controller_port, block_agg_controller_ipc),
            ServiceType.INCOMING_WORK: (incoming_work_port, incoming_work_ipc)
        }

    def resolve(self, socket_base, service_type, bind=False):
        port, ipc = self.params[service_type]
        return services.resolve_tcp_or_ipc_base(socket_base, port, ipc, bind=bind)


class Parameters:
    def __init__(self,
                 socket_base: str,
                 ctx: zmq.asyncio.Context,
                 wallet,
                 contacts: VKBook,
                 network_parameters:NetworkParameters=NetworkParameters()
                 ):

        self.socket_base = socket_base
        self.ctx = ctx
        self.wallet = wallet
        self.network_parameters = network_parameters
        self.contacts = contacts

        self.peer_service_address = self.network_parameters.resolve(socket_base, ServiceType.PEER)
        self.sockets = {}

    def get_masternode_sockets(self, service=None):
        masternodes = {}
        vks = set(self.contacts.masternodes)

        for k in self.sockets.keys():
            if k in vks:
                v = self.sockets.get(k)
                if v is None:
                    return

                if service is not None:
                    v = self.network_parameters.resolve(v, service)

                masternodes[k] = v

        return masternodes

    def get_delegate_sockets(self, service=None):
        delegates = {}
        vks = set(self.contacts.delegates)

        for k in self.sockets.keys():
            if k in vks:
                v = self.sockets.get(k)
                if v is None:
                    return

                if service is not None:
                    v = self.network_parameters.resolve(v, service)

                delegates[k] = v

        return delegates

    def get_all_sockets(self, service=None):
        all = {}

        for k, v in self.sockets.items():
            if service is None:
                all[k] = v
            else:
                all[k] = self.network_parameters.resolve(v, service)

        return all

    def resolve_vk(self, vk, service=None):
        socket = self.sockets.get(vk)

        if socket is None:
            return

        if service is None:
            return socket

        return self.network_parameters.resolve(socket, service)

    async def refresh(self):
        pb_nodes = set(self.contacts.delegates + self.contacts.masternodes)

        try:
            pb_nodes.remove(self.wallet.verifying_key().hex())
        except KeyError:
            pass

        current_nodes = set(self.sockets.keys())

        # Delete / remove old nodes
        to_del = self.old_nodes(pb_nodes, current_nodes)

        for node in to_del:
            self.remove_node(node)

        # Add new nodes
        # to_add = self.new_nodes(pb_nodes, current_nodes)

        coroutines = [self.find_node(m) for m in pb_nodes]

        tasks = asyncio.gather(*coroutines)
        loop = asyncio.get_event_loop()

        if loop.is_running():
            results = await asyncio.ensure_future(tasks)
        else:
            results = loop.run_until_complete(tasks)

        for r in results:
            if r is not None:
                _r = json.loads(r)

                vk, socket = [(k, v) for k, v in _r.items()][0]

                self.sockets.update({vk: socket})

    async def find_node(self, node):
        find_message = ['find', node]
        find_message = json.dumps(find_message).encode()

        return await get(self.peer_service_address, msg=find_message, ctx=self.ctx, timeout=1000)

    @staticmethod
    def new_nodes(phone_book_nodes, current_nodes):
        return phone_book_nodes - current_nodes

    @staticmethod
    def old_nodes(phone_book_nodes, current_nodes):
        return current_nodes - phone_book_nodes

    def remove_node(self, vk):
        entry = self.sockets.get(vk)

        if entry is not None:
            #entry.close()
            del self.sockets[vk]

