"""
Interface to rmcan / proemion byte command mode interfaces
see https://manuals.plus/proemion/byte-command-protocol-binary-commands-manual
"""

import logging

import can

log = logging.getLogger(__name__)


class RmcanBus(can.BusABC):
    def __init__(self, **kwargs):
        """Connects to a CAN bus served by Proemion can interface.
        """
        super().__init__(**kwargs)

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
