from cilantro.logger import get_logger
from multiprocessing import Process
import asyncio
import pickle
import time
# if __name__ == '__main__':
#     log = get_logger("Main")
#
#     log.debug("test debug")
#     log.info("test info")
#     log.warning("test warning")
#     log.error("test error")
#     print("hi")
#     # log.exception("test exception")


log = get_logger("Main")

log.debug("test debug")
log.info("test info")
log.warning("test warning")
log.error("test error")
# log.exception("test exception")
print("how bout dat\n")
# x = 10 / 0

print("\n so thats that \n")

#

#
# loop = asyncio.new_event_loop()
# loop.run_until_complete(do_that())


def something_terrible():
    def nested_horror():
        async def async_death():
            log = get_logger("async_death")
            log.debug("async death start")

            log.debug("starting startup nap")
            await asyncio.sleep(4)
            log.debug("startup nap finished")

            # while True:
            #     log.debug('sleeping...')
            #     await asyncio.sleep(1.5)
            #     log.debug('yawn')
                # log.critical("gunna die")
                # i = 10 / 0
            # log.debug("about to die")
            # i = 10 / 0
            log.debug("async death over")

        async def something_boring():
            log = get_logger("SomethingBoring")
            log.debug("starting something boring")
            await asyncio.sleep(2)
            log.debug("something boring done")

        async def something_sketch():
            log = get_logger("SomethingSketch")
            log.debug("something sketch starting")
            # log.debug("about to blow up")
            # i = 10 / 0
            # log.debug('dead')
            log.debug("something sketch over")


        log = get_logger("NestedHorror")
        log.critical("nested horror commence")

        log.critical("nesthorror start sleep")
        time.sleep(4)
        log.critical("nesthorror done sleep")

        # loop = asyncio.new_event_loop()
        # asyncio.set_event_loop(loop)
        # asyncio.ensure_future(something_boring())
        # asyncio.ensure_future(something_sketch())
        #
        # loop.run_until_complete(async_death())

        # THIS WILL NEVER PRINT (it blocks ofc)
        # log.critical("about to destruct")
        # i = 10 / 0

    log = get_logger("SomethingTerrible")
    log.debug("something terrible spinning up nested_horror")
    p = Process(target=nested_horror)
    p.start()

    log.debug("\n\nPYTHON EQUIVALENT OF JUMPING OFF GOLDEN GATE BRIDGE\n\n")
    pickle.dumps(log)
    # i = 10 / 0



p = Process(target=something_terrible)
p.start()


