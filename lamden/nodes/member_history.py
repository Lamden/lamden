from lamden.storage import BlockStorage
from lamden.network import Network
from lamden.logger.base import get_logger
from lamden.crypto.canonical import hash_members_list

import threading
import asyncio

class MemberHistoryHandler:
    def __init__(self, block_storage: BlockStorage, network: Network):
        self.block_storage = block_storage
        self.network = network

        self.peers = []

        self.current_thread = threading.current_thread()
        self.log = get_logger(f'[{self.current_thread.name}][MEMBER HISTORY]')

    async def catchup_history(self):
        self.log.warning('Starting Member History Catchup...')

        self.peers = self.network.get_all_connected_peers()

        member_history = self.block_storage.member_history.find_previous_block(block_num='99999999999999999999')

        if member_history is None:
            member_history = {
                'number': -1
            }

        while member_history is not None:
            block_num = member_history.get('number')

            member_history = await self.get_next_history_item(block_num=block_num)

            if member_history is not None:
                block_num = member_history.get('number')
                members_list = member_history.get('members_list')

                self.log.info(f'Member History change added at block {block_num}.')

                self.block_storage.member_history.set(block_num=block_num, members_list=members_list)

        self.log.warning('Member History Catchup DONE!')


    def create_members_history_from_blocks(self):
        if self.block_storage.member_history.has_history():
            self.block_storage.member_history.purge()

        block = self.block_storage.get_next_block(v=-1)

        while block is not None:
            self.process_from_block(block=block)

            block = self.block_storage.get_next_block(v=int(block.get('number')))

    def process_from_block(self, block: dict):
        if self.block_storage.is_genesis_block(block=block):
            state_changes = block['genesis']
        else:
            state_changes = block['processed'].get('state')

        for sc in state_changes:
            if sc.get('key') == 'masternodes.S:members':
                self.block_storage.member_history.set(
                    block_num=block.get('number'),
                    members_list=sc.get('value')
                )

    async def get_next_history_item(self, block_num: str = None) -> [dict, None]:
        if block_num is None:
            return None

        history_item = await self.source_history_from_peers(fetch_type='next', block_num=int(block_num))

        return history_item

    async def source_history_from_peers(self, fetch_type: str, block_num: int = 0) -> dict:
        consensus_counts = {}
        consensus_reached = False
        consensus_info = None
        timeout = 5  # Set a reasonable timeout

        while len(self.peers) > 0 and not consensus_reached:
            tasks = []
            for peer in self.peers:
                if fetch_type == 'next':
                    task = asyncio.ensure_future(peer.get_member_history_next(block_num))
                task.__peer__ = peer  # attach the peer directly to the task
                tasks.append(task)

            responses, _ = await asyncio.wait(tasks, timeout=timeout, return_when=asyncio.FIRST_COMPLETED)

            for future in responses:
                try:
                    res = future.result()
                    res_info = res['member_history_info']

                    if res_info is None or self.block_storage.member_history.verify_signature(data=res_info, vk=future.__peer__.server_vk):

                        try:
                            members_list = res_info.get('members_list', [])
                        except AttributeError:
                            members_list = []

                        members_list_hash = hash_members_list(members_list)

                        consensus_counts[members_list_hash] = consensus_counts.get(members_list_hash, 0) + 1
                        if consensus_counts[members_list_hash] / len(self.peers) > 0.51:
                            consensus_reached = True
                            consensus_info = res_info
                    else:
                        self.log.warning(f'Peer {peer.server_vk} providing improperly signed members history info.')
                except Exception as err:
                    self.log.error(err)
                    peer = future.__peer__
                    self.peers.remove(peer)  # remove the unresponsive peer

        if consensus_reached:
            return consensus_info
        else:
            if len(self.peers) == 0:
                raise ValueError('No peers available for member history catchup!')

            return None
