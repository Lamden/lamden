from unittest import TestCase

from tests.inprog.orchestrator import *

import zmq.asyncio


class TestGovernance(TestCase):
    def setUp(self):
        self.ctx = zmq.asyncio.Context()
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

    def tearDown(self):
        self.ctx.destroy()
        self.loop.close()

    def test_add_seat_motion_works(self):
        mns, dls = make_network(2, 2, self.ctx)

        async def test():
            await make_start_awaitable(mns, dls)
            await send_tx(mns[1], mns + dls,
                          contract='election_house',
                          function='vote_policy',
                          kwargs={
                              'policy': 'masternodes', 'value': ('introduce_motion', 2)
                          },
                          sender=mns[0].wallet)

            #await send_tx(mns[1], mns + dls, contract='testing', function='test', sender=Wallet())
            #await send_tx(mns[1], mns + dls, contract='testing', function='test', sender=Wallet())

        loop = asyncio.get_event_loop()
        loop.run_until_complete(test())

# def test_introduce_motion_remove_seat_works_and_sets_position_and_motion_opened(self):
#     self.client.submit(masternodes, constructor_args={
#         'initial_masternodes': [1, 2, 3],
#     })
#
#     mn_contract = self.client.get_contract('masternodes')
#
#     mn_contract.quick_write('S', 'open_seats', 1)
#
#     env = {'now': Datetime._from_datetime(dt.today() + td(days=7))}
#
#     mn_contract.run_private_function(
#         f='introduce_motion',
#         position=3,
#         arg=None,
#         environment=env
#     )
#
#     self.assertEqual(mn_contract.quick_read('S', 'current_motion'), 3)
#     self.assertEqual(mn_contract.quick_read('S', 'motion_opened'), env['now'])