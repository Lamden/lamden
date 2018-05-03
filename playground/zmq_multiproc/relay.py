import threading
import zmq
import asyncio
import zmq.asyncio
from cilantro.logger import get_logger

log = get_logger("Main")


def step1(context=None):
    """Step 1"""
    log = get_logger("STEP 1")
    log.critical("STEP 1 START")
    context = context or zmq.Context.instance()
    # Signal downstream to step 2
    sender = context.socket(zmq.PAIR)
    sender.connect("inproc://step2")

    msg = b"STEP 1 SIG"
    log.info("Sending msg: {}".format(msg))
    sender.send(msg)

def step2(context=None):
    """Step 2"""
    log = get_logger("STEP 2")
    log.critical("STEP 2 START")
    context = context or zmq.Context.instance()
    # Bind to inproc: endpoint, then start upstream thread
    receiver = context.socket(zmq.PAIR)
    receiver.bind("inproc://step2")

    log.info("starting step 1 on diff thread..")
    thread = threading.Thread(target=step1)
    thread.start()

    # Wait for signal
    log.info("waiting for sig...")
    msg = receiver.recv()
    log.info("Got msg: {}".format(msg))

    # Signal downstream to step 3
    sender = context.socket(zmq.PAIR)
    sender.connect("inproc://step3")
    sig = b"STEP 2 SIG"
    log.info("Sending {} to step 3".format(sig))
    sender.send(sig)

def main():
    """ server routine """
    log = get_logger("MAIN")
    log.critical("MAIN START")
    # Prepare our context and sockets
    context = zmq.Context.instance()

    # Bind to inproc: endpoint, then start upstream thread
    receiver = context.socket(zmq.PAIR)
    receiver.bind("inproc://step3")

    log.info("starting step 2 on diff thread...")
    thread = threading.Thread(target=step2)
    thread.start()

    # Wait for signal
    log.info("waiting for sig...")
    string = receiver.recv()
    log.info("Got str: {}".format(string))

    log.critical("Test successful!")

    receiver.close()
    context.term()

async def do_once():
    print("doing once...")
    await asyncio.sleep(2)# time.sleep(2)
    print("done with doing once")

async def do_forever():
    log.debug("Starting do_forever...")
    while True:
        log.debug("do something")
        await asyncio.sleep(1)

if __name__ == "__main__":
    import time

    loop = asyncio.get_event_loop()
    asyncio.set_event_loop(loop)
    # loop.run_until_complete(do_forever())
    # asyncio.ensure_future(loop.run_in_executor(None, do_forever()))
    # loop.run_forever()

    # loop.run_in_executor(None, do_forever)
    log.debug("awaiting do_once")
    loop.run_until_complete(do_once())
    # asyncio.wait(do_once())

    log.debug("running foreva")
    loop.run_until_complete(do_forever())

    # loop.run_forever()

    log.debug('hi it would appear that im unblocked')

    log.debug("sleeping...")
    time.sleep(10)
    log.debug("done sleeping")

    # main()