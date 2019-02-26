import asyncio
import zmq.asyncio
from cilantro.logger import get_logger


async def do_something_that_ensures_a_sketcho():
    log = get_logger("Colin")
    log.info("bout to spawn a sketcho")
    await asyncio.ensure_future(do_that())


async def do_that():
    log = get_logger("Raghu")
    for i in range(4):
        await asyncio.sleep(1)
        log.debug(i)

    log.info("abbout to explode")
    raise Exception("booooooooooooooooooooooom")


async def do_this():
    log = get_logger("Davis")
    while True:
        log.debugv("this")
        await asyncio.sleep(1)




if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    loop.run_until_complete(asyncio.gather(do_something_that_ensures_a_sketcho(), do_this()))