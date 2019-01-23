import asyncio

async def long_thing():
    print('doing a long thing')
    await asyncio.sleep(10)
    print('done with long thing')


async def run():
    try:
        await asyncio.wait_for(long_thing(), 4)
    except asyncio.TimeoutError:
        print("oh shit dat thing timed out")


loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)

loop.run_until_complete(run())

