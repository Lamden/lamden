from . import legacy
from lamden.logger.base import get_logger

log = get_logger('MIGRATE')

def catchup():
    # Get the current latest block stored and the latest block of the network
    log.info('Running migration.')

    current = 0
    latest = legacy.get_latest_block_height()

    log.info(f'Current block: {current}, Latest available block: {latest}')


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