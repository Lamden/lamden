import asyncio

from lamden.logger.base import get_logger
from lamden.nodes import base


class Delegate(base.Node):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.upgrade_manager.node_type = 'delegate'
        self.log = get_logger(f'Delegate {self.wallet.vk_pretty[4:12]}')

    def start_node(self):
        asyncio.ensure_future(self.start())

    async def start(self):
        self.log.debug('Starting')
        await super().start()

        self.driver.clear_pending_state()

        if self.started:
            self.log.info('Done starting...')

    '''
    async def update_sockets(self):
        mns = self.get_masternode_peers()
        iterator = iter(mns.items())
        vk, ip = next(iterator)

        peers = await router.secure_request(
            msg={},
            service=network.PEER_SERVICE,
            cert_dir=self.socket_authenticator.cert_dir,
            wallet=self.wallet,
            ctx=self.ctx,
            vk=vk,
            ip=ip
        )

        if peers is not None:
            self.network.update_peers(peers=peers)
    '''

    async def wait_for_new_block_confirmation(self):
        self.log.info('Waiting for block confirmation...')
        block = await self.new_block_processor.wait_for_next_nbn()
        self.process_new_block(block)

        await self.update_sockets()

    async def run(self):
        self.log.info('Done starting. Beginning participation in consensus.')
        # while self.running:
            # self.log.info(f"Tasks in loop: {len(asyncio.Task.all_tasks())}")
            # await self.loop()
            # await asyncio.sleep(0)
