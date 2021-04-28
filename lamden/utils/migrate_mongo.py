

def catchup(self, mn_seed, mn_vk):
    # Get the current latest block stored and the latest block of the network
    self.log.info('Running catchup.')
    current = self.current_height
    latest = await get_latest_block_height(
        ip=mn_seed,
        vk=mn_vk,
        wallet=self.wallet,
        ctx=self.ctx
    )

    self.log.info(f'Current block: {current}, Latest available block: {latest}')

    if latest == 0 or latest is None or type(latest) == dict:
        self.log.info('No need to catchup. Proceeding.')
        return

    # Increment current by one. Don't count the genesis block.
    if current == 0:
        current = 1

    # Find the missing blocks process them
    for i in range(current, latest + 1):
        block = None
        while block is None:
            block = await get_block(
                block_num=i,
                ip=mn_seed,
                vk=mn_vk,
                wallet=self.wallet,
                ctx=self.ctx
            )
        self.process_new_block(block)