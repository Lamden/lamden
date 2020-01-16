from cilantro_ee.services.overlay.client import OverlayClient

import time
import asyncio


class OverlayClientSync(OverlayClient):
    def __init__(self, ctx):
        super().__init__(self._handle_overlay_reply, self._handle_overlay_reply, ctx=ctx)

        self.events = {}

    def _handle_overlay_reply(self, e):
        self.log.debugv("OverlayClientSync got overlay reply {}".format(e))

        if 'event_id' in e:
            self.events[e['event_id']] = e

        else:
            self.log.debugv("OverlayClientSync got overlay response {} that has no event_id associated. "
                            "Ignoring.".format(e['event']))

    def get_ip_sync(self, vk):
        event_id = self.get_ip_from_vk(vk)
        while event_id not in self.events:
            time.sleep(0.2)
        e = self.events[event_id]
        if e['event'] == 'got_ip':
            return e['ip']
        return None

    async def async_get_ip_sync(self, vk):
        event_id = self.get_ip_from_vk(vk)
        while event_id not in self.events:
            await asyncio.sleep(0.2)
        e = self.events[event_id]
        if e['event'] == 'got_ip':
            return e['ip']
        return None
