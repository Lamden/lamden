import asyncio
import functools
import os
import signal

async def forever():
    while True:
        pass

def ask_exit(signame):
    print("got signal %s: exit" % signame)
    loop.stop()

loop = asyncio.get_event_loop()
for signame in ('SIGINT', 'SIGTERM'):
    loop.add_signal_handler(getattr(signal, signame),
                            functools.partial(ask_exit, signame))

print("Event loop running forever, press Ctrl+C to interrupt.")
print("pid %s: send SIGINT or SIGTERM to exit." % os.getpid())
try:
    loop.run_until_complete(asyncio.wait(forever()))
finally:
    loop.close()

import time
time.sleep(1)
os.kill(os.getpid(), signal.SIGUSR1)