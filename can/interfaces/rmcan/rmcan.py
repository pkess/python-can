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

    @classmethod
    def from_queue(cls, queue):
        while True:
            while True:
                c = queue[0]
                if c == 0x43:
                    log.debug("Found SOF")
                    break
            d_len = queue[1]
            # Frame length = SOF + len + data_len + Checksum + EOF
            f_len = d_len + 4
            if queue.length() < f_len:
                log.debug("Incomplete frame")
                raise Exception()
            eof = data[f_len-1]
            if eof != 0x0D:
                log.warning("EOF not correct. Skipping one byte.")
                queue.popleft()
                break

            cs = 0
            for i in data[2:f_len-3]:
                cs = cs ^ i
            if cs != data[f_len-2]:
                log.warning("Checksum error. Skipping one byte.")
                queue.popleft()
                break

            cmd = queue[2]
            data = queue[3:f_len-3]
            for _ in range(f_len):
                queue.pop()

            frame = RmcanFrame(cmd, data)
            return frame

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
        self.__receive_buffer = bytearray()

        self.__socket.connect((self.__host, self.__port))

        log.info(
            f"RmcanBus: connected with address {self.__socket.getsockname()}"
        )

        super().__init__(None, **kwargs)

    def _recv_internal(self, timeout):
        if len(self.__message_buffer) != 0:
            can_message = self.__message_buffer.popleft()
            return can_message, False

        try:
            self.__receive_buffer += self.__socket.recv(1024)
            if self.__tcp_tune:
                self.__socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_QUICKACK, 1)

            while True:
                frame = RmcanFrame.from_queue(self.__receive_buffer)
                if frame.command == 0x00:
                    log.debug("Received standard frame")
                    arbit_id = struct.unpack(">H", frame.data[0:1])
                    msg = can.Message(
                            arbitration_id=arbit_id,
                            is_extended_frame=False,
                            data=frame.data[2:],
                            )
                    return None, False
                elif frame.command == 0x02:
                    log.debug("Received extended frame")
                else:
                    log.warning("Received unsupported frame with command %s",
                                (frame.command))
        except Exception:
            return None, False

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
