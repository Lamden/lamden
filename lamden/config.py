import pathlib

BLOCK_SERVICE = 'catchup'
GET_LATEST_BLOCK = 'get_latest_block'
GET_BLOCK = "get_block"
GET_CONSTITUTION = "get_constitution"
GET_ALL_PEERS = "get_all_peers"
NEW_BLOCK_SERVICE = 'new_blocks'
NEW_BLOCK_EVENT = 'new_block'
NEW_BLOCK_REORG_EVENT = 'block_reorg'
WORK_SERVICE = 'work'
CONTENDER_SERVICE = 'contenders'
STORAGE_HOME = pathlib.Path().home().joinpath('.lamden')