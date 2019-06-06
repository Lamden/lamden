from cilantro_ee.utils.lprocess import LProcess
from cilantro_ee.nodes.base import NodeBase
from cilantro_ee.constants.system_config import NUM_SB_BUILDERS
from cilantro_ee.nodes.delegate.block_manager import BlockManager


class Delegate(NodeBase):

    # This call should not block!
    def start_node(self):
        self._start_bm()
        return NUM_SB_BUILDERS + 1

    def _start_bm(self):
        self.log.info("Starting block manager process")
        self.bm = LProcess(target=BlockManager, name='BlockManager',
                                kwargs={'signing_key': self.signing_key,
                                        'ip': self.ip})
        self.bm.start()
