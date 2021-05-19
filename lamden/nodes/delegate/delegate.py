import asyncio

from lamden import router, network
from lamden.logger.base import get_logger
from lamden.nodes import base


class Delegate(base.Node):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.upgrade_manager.node_type = 'delegate'
        self.log = get_logger(f'Delegate {self.wallet.vk_pretty[4:12]}')

    async def start(self):
        self.log.debug('Starting')
        await super().start()

        members = self.driver.get_var(contract='delegates', variable='S', arguments=['members'])

        self.log.info('\n------ MEMBERS ------')
        self.log.debug(members)
        self.log.info('\n------ ME ------')
        self.log.debug(self.wallet.verifying_key)

        assert self.wallet.verifying_key in members, 'You are not a delegate!'

        self.log.info("Ensure run future")
        asyncio.ensure_future(self.run())


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

    async def wait_for_new_block_confirmation(self):
        self.log.info('Waiting for block confirmation...')
        block = await self.new_block_processor.wait_for_next_nbn()
        self.process_new_block(block)

        await self.update_sockets()

    async def run(self):
        self.log.info('Done starting. Beginning participation in consensus.')
        while self.running:
            tasks = asyncio.Task.all_tasks()
            self.log(f"Tasks in loop: {tasks}")
            await self.loop()
            await asyncio.sleep(0)

    def stop(self):
        self.router.stop()
