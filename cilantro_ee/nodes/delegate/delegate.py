from cilantro_ee.utils.lprocess import LProcess
from cilantro_ee.nodes.base import NodeBase
from cilantro_ee.nodes.delegate.sub_block_builder_manager import SubBlockBuilderManager


class Delegate(NodeBase):

    # This call should not block!
    def start_node(self):
        self._start_bm()
        return 1

    def _start_bm(self):
        self.log.info("Starting sub-block builder manager process")
        self.bm = LProcess(target=SubBlockBuilderManager,
                           name='SubBlockBuilderManager',
                           kwargs={'signing_key': self.signing_key, 'ip': self.ip})
        self.bm.start()
