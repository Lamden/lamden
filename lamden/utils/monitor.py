"""Module holding utility and convenience functions for zmq event monitoring."""

# Copyright (C) PyZMQ Developers
# Distributed under the terms of the Modified BSD License.

# import asyncio
import struct

# from typing import Any, Awaitable, Coroutine, Union, overload
from typing import List

import zmq
import zmq.asyncio
from zmq._typing import TypedDict
from zmq.error import _check_version


class _MonitorMessage(TypedDict):
    def __init__(event: int, value: int, endpoint: bytes):
        self.event = event
        self.value = value
        self.endpoint = endpoint


def parse_monitor_message(msg: List[bytes]) -> _MonitorMessage:
    """decode zmq_monitor event messages.

    Parameters
    ----------
    msg : list(bytes)
        zmq multipart message that has arrived on a monitor PAIR socket.

        First frame is::

            16 bit event id
            32 bit event value
            no padding

        Second frame is the endpoint as a bytestring

    Returns
    -------
    event : dict
        event description as dict with the keys `event`, `value`, and `endpoint`.
    """
    if len(msg) != 2 or len(msg[0]) != 6:
        raise RuntimeError("Invalid event message format: %s" % msg)
    event_id, value = struct.unpack("=hi", msg[0])
    event = _MonitorMessage(
        'event': event_id,
        'value': value,
        'endpoint': msg[1],
    )
    return event


async def recv_monitor_message_async(
    socket: zmq.Socket, flags: int = 0
) -> _MonitorMessage:
    """Receive and decode the given raw message from the monitoring socket and return a dict.

    Requires libzmq ≥ 4.0

    dict will have the following entries:
      event     : int, the event id as described in libzmq.zmq_socket_monitor
      value     : int, the event value associated with the event, see libzmq.zmq_socket_monitor
      endpoint  : string, the affected endpoint

    Parameters
    ----------
    socket : zmq PAIR socket
        The PAIR socket (created by other.get_monitor_socket()) on which to recv the message
    flags : bitfield (int)
        standard zmq recv flags

    Returns
    -------

    future_event: an instance of asyncio.Future, the result of Future would have:
        event description as dict with the keys `event`, `value`, and `endpoint`.

    """
    _check_version((4, 0), 'libzmq event API')
    # will always return a list
    msg = await socket.recv_multipart(flags)  # type: ignore
    # 4.0-style event API
    return parse_monitor_message(msg)


def recv_monitor_message(socket: zmq.Socket, flags: int = 0) -> _MonitorMessage:
    """Receive and decode the given raw message from the monitoring socket and return a dict.

    Requires libzmq ≥ 4.0

    The returned dict will have the following entries:
      event     : int, the event id as described in libzmq.zmq_socket_monitor
      value     : int, the event value associated with the event, see libzmq.zmq_socket_monitor
      endpoint  : string, the affected endpoint

    Parameters
    ----------
    socket : zmq PAIR socket
        The PAIR socket (created by other.get_monitor_socket()) on which to recv the message
    flags : bitfield (int)
        standard zmq recv flags

    Returns
    -------
    event : dict
        event description as dict with the keys `event`, `value`, and `endpoint`.

    if socket.context is of zmq.asyncio.Context type, return asyncio.Future
    """

    # transparently handle asyncio socket,
    # returns a future instead of a dict
    if isinstance(socket.context, zmq.asyncio.Context):
        return recv_monitor_message_async(socket, flags)  # type: ignore

    _check_version((4, 0), 'libzmq event API')
    # will always return a list
    msg = socket.recv_multipart(flags)
    # 4.0-style event API
    return parse_monitor_message(msg)


__all__ = ['parse_monitor_message', 'recv_monitor_message']