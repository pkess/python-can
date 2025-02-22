"""
Interface to rmcan / proemion byte command mode interfaces
see https://manuals.plus/proemion/byte-command-protocol-binary-commands-manual
"""

import logging
import socket
import struct
import time

from collections import deque
import can

log = logging.getLogger(__name__)


class RmcanFrame(object):
    def __init__(self, command, data):
        self.command = command
        self.data = data

    def to_raw(self):
        b = bytearray([0x43, self.command])
        b.append(len(self.data))
        b.extend(self.data)
        cs = 0
        for i in b:
            cs = cs ^ i
        b.append(cs)
        b.append(0x0D)
        print(b)
        return b


class RmcanBus(can.BusABC):
    def __init__(self, channel=None, host="localhost", port=30000, **kwargs):
        """Connects to a CAN bus served by Proemion can interface.
        """
        self.__host = host
        self.__port = port


        self.__socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

        self.__message_buffer = deque()
        self.__receive_buffer = ""  # i know string is not the most efficient here

        self.__socket.connect((self.__host, self.__port))

        log.info(
            f"RmcanBus: connected with address {self.__socket.getsockname()}"
        )

        super().__init__(None, **kwargs)

    def _recv_internal(self, timeout):
        pass

    def send(self, msg, timeout=None):
        """Transmit a message to the CAN bus.

        :param msg: A message object.
        :param timeout: Ignored
        """
        data = bytearray(struct.pack('>H', msg.arbitration_id))
        data.extend(msg.data)
        if msg.is_remote_frame:
            log.error("RmcanBus: remote frames are not supported")
            return

        if msg.is_error_frame:
            log.error("RmcanBus: error frames are not supported")
            return

        if msg.is_extended_id:
            frame = RmcanFrame(0x02, data)
        else:
            frame = RmcanFrame(0x00, data)

        self.__socket.sendall(bytes(frame.to_raw()))

    def shutdown(self):
        """Stops all active periodic tasks and closes the socket."""
        super().shutdown()
