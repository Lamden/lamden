from cilantro_ee.utils.lprocess import LProcess

from cilantro_ee.nodes.scheduler.task_sender import TaskSender
from cilantro_ee.nodes.state_sync import StateSyncNode


class Scheduler(StateSyncNode):

    def start_node(self):
        super().start_node()
        self.log.info("Starting TaskSender process...")
        self.task_sender = LProcess(target=TaskSender, name='TaskSender',
                                    kwargs={'signing_key': self.signing_key, 'ip': self.ip})
        self.task_sender.start()
