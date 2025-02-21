"""
Interface to rmcan / proemion byte command mode interfaces
see https://manuals.plus/proemion/byte-command-protocol-binary-commands-manual
"""

import logging
import socket
import time

from collections import deque
import can

log = logging.getLogger(__name__)


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
        pass

    def shutdown(self):
        """Stops all active periodic tasks and closes the socket."""
        super().shutdown()
