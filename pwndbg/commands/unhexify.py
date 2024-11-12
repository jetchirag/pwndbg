"""
Unhexify data such as "00 70 75 c1  cd ef 59 00" and returns it as pointer like 0x0059efcdc1757000
"""

from __future__ import annotations

import argparse

import pwndbg.commands
import pwndbg.lib.strings

parser = argparse.ArgumentParser(description="Returns hex data as pointer")

parser.add_argument("data", type=str, help="Hex data to unhexify")


@pwndbg.commands.ArgparsedCommand(parser)
# @pwndbg.commands.OnlyWhenRunning
def unhexify(data):
    """
    Unhexify hex data
    """

    print(pwndbg.lib.strings.hex_string_to_pointer(data))
