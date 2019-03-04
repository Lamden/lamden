from cilantro_ee.utils.lprocess import LProcess
from cilantro_ee.nodes.base import NodeBase
from cilantro_ee.nodes.delegate.block_manager import BlockManager


# TODO this can probly be refactored to multi-inherit from BlockManager and look a bit nicer
class Delegate(NodeBase):

    # This call should not block!
    def start_node(self):
        self._start_bm()

    def _start_bm(self):
        self.log.info("Starting block manager process")
        self.bm = LProcess(target=BlockManager, name='BlockManager',
                                kwargs={'signing_key': self.signing_key,
                                        'ip': self.ip})
        self.bm.start()

