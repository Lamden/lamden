from cilantro.logger import get_logger
from cilantro.nodes.utilitynodes import BaseNode, DebugMsg
from cilantro.nodes.utilitynodes.mixins import GroupMixin
import asyncio, uuid, os, warnings

log = get_logger("Main")
log.debug("-- MAIN THREAD ({}) --".format(os.getenv('HOST_IP', '127.0.0.1')))
ip_list = os.getenv('NODE','127.0.0.1').split(',')[1:8]

class PubNode(BaseNode, GroupMixin):
    def __init__(self, mode='rolling_group'):
        super(PubNode, self).__init__()
        self.mode = mode # 'rolling_group' or 'random_group' or 'random_subgroup' or 'all_target_groups'
        self.idxs = []
        self.regroup(self.load_ips(ip_list))
        # self.regroup(discover())

    async def debug_forever_pub(self):
        while True:
            payload = 'random-payload-{}'.format(uuid.uuid4().hex)
            self.designate_next_group()
            self.composer.pub(data=DebugMsg(payload), filter='')
            await asyncio.sleep(1)

class SubNode(BaseNode, GroupMixin):
    def __init__(self, pub_ip, mode='rolling_group'):
        super(SubNode, self).__init__()
        self.regroup(self.load_ips(ip_list))
        # self.regroup(discover())
        for idx in self.nodes[os.getenv('HOST_IP')]['groups']:
            self.composer.add_sub(url="tcp://{}:{}".format(pub_ip, self.groups[idx]['port']), filter='')

if __name__ == "__main__":
    publisher = PubNode()
    # nodes = [SubNode() for i in range(8)]
