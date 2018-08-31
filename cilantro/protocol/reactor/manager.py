import asyncio, os, logging
import zmq.asyncio
from cilantro.logger import get_logger
from cilantro.protocol.reactor.executor import Executor


class ExecutorManager:

    def __init__(self, loop, context, signing_key, router, name='Worker'):
        self.log = get_logger(name)

        self.loop = loop
        self.context = context
        self.router = router
        self.executors = {name: executor(loop=self.loop, context=self.context, router=self.router)
                          for name, executor in Executor.registry.items()}

    def start(self):
        try:
            self.log.info("Starting event loop")
            self.loop.run_forever()
        except Exception as e:
            self.log.fatal("Exception running main event loop... error:\n{}\n".format(e))
        finally:
            # TODO clean thangs up
            pass

    def teardown(self):
        raise NotImplementedError("Need to code this up")

        # TODO implement
        # loop over executors, call teardown on each
        # cancel any futures
        # signal to any subprocs to teardown also?
