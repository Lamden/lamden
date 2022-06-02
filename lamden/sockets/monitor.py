import zmq
import zmq.asyncio
import asyncio
from zmq.utils import monitor
from lamden.utils.monitor import recv_monitor_message_async
from lamden.logger.base import get_logger

monitor_errors_map = {
    'CONNECTED': zmq.EVENT_CONNECTED,
    'CONNECT_DELAYED': zmq.EVENT_CONNECT_DELAYED,
    'CONNECT_RETRIED': zmq.EVENT_CONNECT_RETRIED,
    'LISTENING': zmq.EVENT_LISTENING,
    'BIND_FAILED': zmq.EVENT_BIND_FAILED,
    'ACCEPTED': zmq.EVENT_ACCEPTED,
    'ACCEPT_FAILED': zmq.EVENT_ACCEPT_FAILED,
    'CLOSED': zmq.EVENT_CLOSED,
    'CLOSE_FAILED': zmq.EVENT_CLOSE_FAILED,
    'DISCONNECTED': zmq.EVENT_DISCONNECTED,
    'MONITOR_STOPPED': zmq.EVENT_MONITOR_STOPPED
}

class SocketMonitor:
    def __init__(self, socket_type: str = ""):
        self.loop = None
        self.sockets_to_monitor = list()
        self.poller = zmq.asyncio.Poller()
        self.get_event_loop()
        self.socket_type = socket_type
        self.running = False

        self.check_for_events_task = None
        self.check_for_events_task_stopped = True

    def get_event_loop(self) -> None:
        try:
            self.loop = asyncio.get_event_loop()
            if self.loop.is_closed():
                self.set_event_loop()
        except RuntimeError:
            self.set_event_loop()

    def set_event_loop(self) -> None:
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

    def log(self, log_type: str, message: str) -> None:
        logger = get_logger(f'{self.socket_type}_SOCKET_MONITOR')
        print(f'[{self.socket_type}_SOCKET_MONITOR] {message}\n')

        if log_type == 'info':
            logger.info(message)
        if log_type == 'error':
            logger.error(message)
        if log_type == 'warning':
            logger.warning(message)

    def start(self) -> None:
        if self.check_for_events_task is None or self.check_for_events_task.done():
            self.running = True
            self.check_for_events_task = asyncio.ensure_future(self.check_for_events())
            self.check_for_events_task.add_done_callback(self.task_done)

    async def check_for_events(self) -> None:
        self.check_for_events_task_stopped = False

        while self.running:
            sockets = await self.poller.poll(timeout=10)

            for socket in sockets:
                monitor_socket = socket[0]
                monitor_result = await monitor.recv_monitor_message(monitor_socket)
                if monitor_result:
                    self.print_event_message(socket=socket, monitor_result=monitor_result)

            await asyncio.sleep(0)

        self.log('info', "No longer checking for monitor events.")

    def print_event_message(self, socket, monitor_result):
        event_num = monitor_result.get("event")
        event_value = monitor_result.get("value")
        if event_num is not None:
            for key, value in monitor_errors_map.items():
                if event_num == value:
                    endpoint = monitor_result.get('endpoint').decode('UTF-8')
                    self.log('info', f'[{socket}]{endpoint}: {key}-{event_value}')

    def monitor(self, socket: zmq.Socket) -> None:
        socket_monitor = socket.get_monitor_socket()
        socket_monitor.linger = 0
        self.poller.register(socket_monitor, zmq.POLLIN)
        self.sockets_to_monitor.append(socket_monitor)

    def stop_monitoring(self, socket: zmq.Socket) -> None:
        socket_monitor = socket.get_monitor_socket()
        self.unregister_socket_from_poller(socket=socket_monitor)
        self.sockets_to_monitor.remove(socket_monitor)

    def unregister_socket_from_poller(self, socket: zmq.Socket):
        try:
            self.poller.unregister(socket=socket)
        except KeyError:
            pass

    def unregister_all_sockets_from_poller(self):
        for socket in self.sockets_to_monitor:
            self.unregister_socket_from_poller(socket=socket)

    def task_done(self, future) -> None:
        self.check_for_events_task_stopped = True

    async def await_task_stopping(self) -> None:
        while not self.check_for_events_task_stopped:
            await asyncio.sleep(0)

    async def stop(self) -> None:
        self.running = False
        await self.await_task_stopping()
        self.unregister_all_sockets_from_poller()

        self.log('info', "Stopped.")

