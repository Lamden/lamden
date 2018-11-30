from cilantro.nodes.base import NodeBase, NodeTypes
from cilantro.nodes.delegate.block_manager import BlockManager
from cilantro.storage.vkbook import VKBook


# TODO this can probly be refactored to multi-inherit from BlockManager and look a bit nicer
class Delegate(NodeBase):
    def start(self):
        self.bm = BlockManager(ip=self.ip, manager=self.manager)  # This blocks

