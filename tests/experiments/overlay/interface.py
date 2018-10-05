from cilantro.protocol.overlay.daemon import OverlayInterface
from cilantro.logger.base import get_logger
from threading import Thread
import asyncio

log = get_logger(__name__)

def event_handler(e):
    log.important(e)

OverlayInterface.start_service(sk='06391888e37a48cef1ded85a375490df4f9b2c74f7723e88c954a055f3d2685a')
node = OverlayInterface.get_node_from_vk(vk='82540bb5a9c84162214c5540d6e43be49bbfe19cf49685660cab608998a65144')
