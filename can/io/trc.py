# coding: utf-8

"""
Reader and writer for can logging files in peak trc format
"""

from __future__ import absolute_import

from datetime import datetime
import time
import logging

from ..message import Message
from ..listener import Listener
from ..util import channel2int
from .generic import BaseIOHandler


logger = logging.getLogger('can.io.trc')


# Format for trace file header.
#
# Fields:
# - days: Number of days that have passed since 30. December 1899
# - milliseconds: milliseconds since 00:00:00 of day
# - filepath: full path to log file
# - starttime: starttime of trace formatted as %d.%m.%Y %H:%M:%S
FMT_TRC_HEADER_VER_1_1 = """\
;$FILEVERSION=1.1
;$STARTTIME={days}.{milliseconds}
;
;   {filepath}
;
;   Start time: {starttime}
;   Message Number
;   |         Time Offset (ms)
;   |         |        Type
;   |         |        |        ID (hex)
;   |         |        |        |     Data Length Code
;   |         |        |        |     |   Data Bytes (hex) ...
;   |         |        |        |     |   |
;---+--   ----+----  --+--  ----+---  +  -+ -- -- -- -- -- -- --"""


class TRCReader(BaseIOHandler):
    """
    Iterator of CAN messages from a TRC logging file.
    """

    def __init__(self, file):
        """
        :param file: a path-like object or as file-like object to read from
                     If this is a file-like object, is has to opened in text
                     read mode, not binary read mode.
        """
        super(TRCReader, self).__init__(file, mode='r')

    @staticmethod
    def _extract_can_id(str_can_id):
        if str_can_id[-1:].lower() == 'x':
            is_extended = True
            can_id = int(str_can_id[0:-1], 16)
        else:
            is_extended = False
            can_id = int(str_can_id, 16)
        return can_id, is_extended

    def __iter__(self):
        for line in self.file:
            temp = line.strip()
            if not temp or not temp[0].isdigit():
                continue
            is_fd = False
            try:
                timestamp, channel, dummy = temp.split(None, 2) # , frameType, dlc, frameData
                if channel == "CANFD":
                    timestamp, _, channel, _, dummy = temp.split(None, 4)
                    is_fd = True

            except ValueError:
                # we parsed an empty comment
                continue

            timestamp = float(timestamp)
            try:
                # See ASCWriter
                channel = int(channel) - 1
            except ValueError:
                pass

            if dummy.strip()[0:10].lower() == 'errorframe':
                msg = Message(timestamp=timestamp, is_error_frame=True,
                              channel=channel)
                yield msg

            elif (not isinstance(channel, int)
                  or dummy.strip()[0:10].lower() == 'statistic:'
                  or dummy.split(None, 1)[0] == "J1939TP"
            ):
                pass

            elif dummy[-1:].lower() == 'r':
                can_id_str, _ = dummy.split(None, 1)
                can_id_num, is_extended_id = self._extract_can_id(can_id_str)
                msg = Message(timestamp=timestamp,
                              arbitration_id=can_id_num & CAN_ID_MASK,
                              is_extended_id=is_extended_id,
                              is_remote_frame=True,
                              channel=channel)
                yield msg

            else:
                brs = None
                esi = None
                data_length = 0
                try:
                    # this only works if dlc > 0 and thus data is available
                    if not is_fd:
                        can_id_str, _, _, dlc, data = dummy.split(None, 4)
                    else:
                        can_id_str, frame_name, brs, esi, dlc, data_length, data = dummy.split(
                            None, 6
                        )
                        if frame_name.isdigit():
                            # Empty frame_name
                            can_id_str, brs, esi, dlc, data_length, data = dummy.split(
                                None, 5
                            )
                except ValueError:
                    # but if not, we only want to get the stuff up to the dlc
                    can_id_str, _, _, dlc       = dummy.split(None, 3)
                    # and we set data to an empty sequence manually
                    data = ''
                dlc = int(dlc, 16)
                if is_fd:
                    # For fd frames, dlc and data length might not be equal and
                    # data_length is the actual size of the data
                    dlc = int(data_length)
                frame = bytearray()
                data = data.split()
                for byte in data[0:dlc]:
                    frame.append(int(byte, 16))

                can_id_num, is_extended_id = self._extract_can_id(can_id_str)

                yield Message(
                    timestamp=timestamp,
                    arbitration_id=can_id_num & CAN_ID_MASK,
                    is_extended_id=is_extended_id,
                    is_remote_frame=False,
                    dlc=dlc,
                    data=frame,
                    is_fd=is_fd,
                    channel=channel,
                    bitrate_switch=is_fd and brs == "1",
                    error_state_indicator=is_fd and esi == "1",
                )

        self.stop()


class TRCWriter(BaseIOHandler, Listener):
    """Logs CAN data to text file (.trc).

    The measurement starts with the timestamp of the first registered message.
    If a message has a timestamp smaller than the previous one or None,
    it gets assigned the timestamp that was written for the last message.
    It the first message does not have a timestamp, it is set to zero.
    """

    FORMAT_MESSAGE = "{channel}  {id:<15} Rx   {dtype} {data}"
    FORMAT_DATE = "%a %b %m %I:%M:%S.{} %p %Y"
    FORMAT_EVENT = "{timestamp: 9.6f} {message}\n"

    def __init__(self, file, channel=1):
        """
        :param file: a path-like object or as file-like object to write to
                     If this is a file-like object, is has to opened in text
                     write mode, not binary write mode.
        :param channel: a default channel to use when the message does not
                        have a channel set
        """
        super(TRCWriter, self).__init__(file, mode='w')
        self.channel = channel

        # write start of file header
        now = datetime.now().strftime("%a %b %m %I:%M:%S.%f %p %Y")
        self.file.write("date %s\n" % now)
        self.file.write("base hex  timestamps absolute\n")
        self.file.write("internal events logged\n")

        # the last part is written with the timestamp of the first message
        self.header_written = False
        self.last_timestamp = None
        self.started = None

    def stop(self):
        if not self.file.closed:
            self.file.write("End TriggerBlock\n")
        super(ASCWriter, self).stop()

    def log_event(self, message, timestamp=None):
        """Add a message to the log file.

        :param str message: an arbitrary message
        :param float timestamp: the absolute timestamp of the event
        """

        if not message: # if empty or None
            logger.debug("ASCWriter: ignoring empty message")
            return

        # this is the case for the very first message:
        if not self.header_written:
            self.last_timestamp = (timestamp or 0.0)
            self.started = self.last_timestamp
            mlsec = repr(self.last_timestamp).split('.')[1][:3]
            formatted_date = time.strftime(self.FORMAT_DATE.format(mlsec), time.localtime(self.last_timestamp))
            self.file.write("Begin Triggerblock %s\n" % formatted_date)
            self.header_written = True
            self.log_event("Start of measurement") # caution: this is a recursive call!

        # Use last known timestamp if unknown
        if timestamp is None:
            timestamp = self.last_timestamp

        # turn into relative timestamps if necessary
        if timestamp >= self.started:
            timestamp -= self.started

        line = self.FORMAT_EVENT.format(timestamp=timestamp, message=message)
        self.file.write(line)

    def on_message_received(self, msg):

        if msg.is_error_frame:
            self.log_event("{}  ErrorFrame".format(self.channel), msg.timestamp)
            return

        if msg.is_remote_frame:
            dtype = 'r'
            data = []
        else:
            dtype = "d {}".format(msg.dlc)
            data = ["{:02X}".format(byte) for byte in msg.data]

        arb_id = "{:X}".format(msg.arbitration_id)
        if msg.is_extended_id:
            arb_id += 'x'

        channel = channel2int(msg.channel)
        if channel is None:
            channel = self.channel
        else:
            # Many interfaces start channel numbering at 0 which is invalid
            channel += 1

        serialized = self.FORMAT_MESSAGE.format(channel=channel,
                                                id=arb_id,
                                                dtype=dtype,
                                                data=' '.join(data))

        self.log_event(serialized, msg.timestamp)
