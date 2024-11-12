from __future__ import annotations

import re


def strip_colors(text):
    """Remove all ANSI color codes from the text"""
    return re.sub(r"\x1b[^m]*m", "", text)


def hex_string_to_pointer(hex_string):
    data = bytes.fromhex(hex_string)

    # Convert the byte data to an integer - little endian
    pointer = int.from_bytes(data, byteorder="little")

    return f"0x{pointer:016x}"
