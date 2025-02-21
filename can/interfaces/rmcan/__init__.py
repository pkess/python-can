"""
Interface to rmcan / proemion byte command mode interfaces
see https://manuals.plus/proemion/byte-command-protocol-binary-commands-manual
"""

__all__ = [
    "RmcanBus",
    "rmcan",
]

from .rmcan import RmcanBus
