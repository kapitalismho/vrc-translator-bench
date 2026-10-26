from __future__ import annotations

import base64
import struct


def _string(data, offset):
    end = data.index(b"\0", offset)
    return data[offset:end].decode("utf-8"), (end + 4) & ~3


def decode(data):
    if data.startswith(b"#bundle\0"):
        if len(data) < 16:
            raise ValueError("Truncated OSC bundle")
        offset = 16
        result = []
        while offset < len(data):
            size = struct.unpack_from(">I", data, offset)[0]
            offset += 4
            if size == 0 or offset + size > len(data):
                raise ValueError("Invalid OSC bundle element")
            result.extend(decode(data[offset:offset + size]))
            offset += size
        return result
    address, offset = _string(data, 0)
    tags, offset = _string(data, offset)
    if not address.startswith("/") or not tags.startswith(","):
        raise ValueError("Invalid OSC address/type tags")
    args = []
    for tag in tags[1:]:
        if tag in "TFNI":
            args.append({"T": True, "F": False, "N": None, "I": "Infinity"}[tag])
        elif tag in "sS":
            value, offset = _string(data, offset)
            args.append(value)
        elif tag == "b":
            size = struct.unpack_from(">I", data, offset)[0]
            offset += 4
            if offset + size > len(data):
                raise ValueError("Truncated OSC blob")
            args.append({"base64": base64.b64encode(data[offset:offset + size]).decode("ascii")})
            offset = (offset + size + 3) & ~3
        elif tag in "ifhdtrcm":
            fmt = {"i": ">i", "f": ">f", "h": ">q", "d": ">d", "t": ">Q", "r": ">I", "c": ">I", "m": ">I"}[tag]
            value = struct.unpack_from(fmt, data, offset)[0]
            offset += struct.calcsize(fmt)
            if isinstance(value, float) and not (-float("inf") < value < float("inf")):
                value = str(value)
            args.append(value)
        else:
            raise ValueError(f"Unsupported OSC type tag: {tag}")
    if offset != len(data):
        raise ValueError("Trailing OSC bytes")
    return [(address, args)]


def encode(address, args):
    def text(value):
        raw = value.encode("utf-8") + b"\0"
        return raw + b"\0" * (-len(raw) % 4)
    tags, payload = ",", b""
    for value in args:
        if isinstance(value, bool):
            tags += "T" if value else "F"
        elif isinstance(value, str):
            tags += "s"
            payload += text(value)
        elif isinstance(value, int):
            tags += "i"
            payload += struct.pack(">i", value)
        else:
            raise ValueError("Unsupported outgoing OSC argument")
    return text(address) + text(tags) + payload

