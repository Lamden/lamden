from cilantro_ee.networking.network import Network
from cilantro_ee.catchup import BlockFetcher

from cilantro_ee.nodes.new_block_inbox import NBNInbox
from cilantro_ee.storage import VKBook
from cilantro_ee.contracts import sync
from cilantro_ee.networking.parameters import Parameters, ServiceType, NetworkParameters
import cilantro_ee
import zmq.asyncio
import asyncio
from cilantro_ee.sockets.authentication import SocketAuthenticator
from cilantro_ee.storage.contract import BlockchainDriver
from contracting.client import ContractingClient

from cilantro_ee.rewards import RewardManager


from cilantro_ee.logger.base import get_logger

from copy import deepcopy


class Node:
    def __init__(self, socket_base, ctx: zmq.asyncio.Context, wallet, constitution: dict, overwrite=False,
                 bootnodes=[], network_parameters=NetworkParameters(), driver=BlockchainDriver(), debug=True):

        self.driver = driver
        self.client = ContractingClient(driver=self.driver, submission_filename=cilantro_ee.contracts.__path__[0] + '/submission.s.py')
        self.log = get_logger('NODE')
        self.log.propagate = debug
        self.log.info(constitution)
        self.socket_base = socket_base
        self.wallet = wallet
        self.ctx = ctx

        # Sync contracts

        print(constitution)

        sync.submit_from_genesis_json_file(cilantro_ee.contracts.__path__[0] + '/genesis.json', client=self.client)
        sync.submit_node_election_contracts(
            initial_masternodes=constitution['masternodes'],
            boot_mns=constitution['masternode_min_quorum'],
            initial_delegates=constitution['delegates'],
            boot_dels=constitution['delegate_min_quorum'],
            client=self.client
        )

        self.driver.commit()
        self.driver.clear_pending_state()

        self.contacts = VKBook(boot_mn=constitution['masternode_min_quorum'],
                               boot_del=constitution['delegate_min_quorum'],
                               client=self.client)
        self.current_masters = deepcopy(self.contacts.masternodes)
        self.current_delegates = deepcopy(self.contacts.delegates)

        self.parameters = Parameters(socket_base, ctx, wallet, contacts=self.contacts)

        self.socket_authenticator = SocketAuthenticator(wallet=wallet, contacts=self.contacts, ctx=self.ctx)
        self.socket_authenticator.sync_certs()

        self.elect_masternodes = self.client.get_contract('elect_masternodes')
        self.on_deck_master = self.elect_masternodes.quick_read('top_candidate')

        self.elect_delegates = self.client.get_contract('elect_delegates')
        self.on_deck_delegate = self.elect_delegates.quick_read('top_candidate')
        # stuff

        self.network_parameters = network_parameters

        self.bootnodes = bootnodes
        self.constitution = constitution
        self.overwrite = overwrite

        self.block_fetcher = BlockFetcher(
            wallet=self.wallet,
            ctx=self.ctx,
            parameters=self.parameters,
        )

        self.network = Network(
            wallet=self.wallet,
            ctx=self.ctx,
            socket_base=socket_base,
            bootnodes=self.bootnodes,
            params=self.network_parameters,
            initial_del_quorum=deepcopy(self.contacts.delegate_quorum_min),
            initial_mn_quorum=deepcopy(self.contacts.masternode_quorum_min),
            mn_to_find=deepcopy(self.contacts.masternodes),
            del_to_find=deepcopy(self.contacts.delegates),
        )

        self.nbn_inbox = NBNInbox(
            socket_id=self.network_parameters.resolve(
                self.socket_base,
                service_type=ServiceType.BLOCK_NOTIFICATIONS,
                bind=True),
            ctx=self.ctx,
            driver=self.driver,
            contacts=self.contacts,
            wallet=wallet
        )

        self.reward_manager = RewardManager(driver=self.driver, vkbook=self.contacts, debug=False)

        self.running = False

    async def start(self):
        await self.network.start()

        # Catchup
        if len(self.contacts.masternodes) > 1 or self.wallet.verifying_key().hex() in self.contacts.delegates:
            await self.block_fetcher.sync()

        asyncio.ensure_future(self.nbn_inbox.serve())

        self.running = True

    def stop(self):
        self.network.stop()
        self.nbn_inbox.stop()
        self.running = False

    def update_sockets(self):
        # UPDATE SOCKETS IF NEEDED
        mn = self.elect_masternodes.quick_read('top_candidate')
        dl = self.elect_delegates.quick_read('top_candidate')

        update_mn = self.on_deck_master != mn and mn is not None
        update_del = self.on_deck_delegate != dl and dl is not None

        ## Check if
        nodes_changed = self.contacts.masternodes != self.current_masters \
                        or self.contacts.delegates != self.current_delegates

        if nodes_changed:
            self.current_masters = deepcopy(self.contacts.masternodes)
            self.current_delegates = deepcopy(self.contacts.delegates)

        if update_mn or update_del or nodes_changed:
            self.socket_authenticator.sync_certs()

            if update_mn:
                self.socket_authenticator.add_verifying_key(mn)
                self.on_deck_master = mn

            if update_del:
                self.socket_authenticator.add_verifying_key(dl)
                self.on_deck_master = dl

    def issue_rewards(self, block):
        # ISSUE REWARDS
        # stamps = self.reward_manager.stamps_in_block(block)
        # self.reward_manager.set_pending_rewards(stamps / self.reward_manager.stamps_per_tau)
        self.reward_manager.issue_rewards(block=block)
