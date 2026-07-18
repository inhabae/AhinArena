import struct


def static_x86_64_elf(payload: bytes = b"\x90") -> bytes:
    """Return a minimal ELF-shaped artifact accepted by admission validation."""
    data = bytearray(120 + len(payload))
    data[:16] = b"\x7fELF\x02\x01\x01" + b"\x00" * 9
    struct.pack_into("<HHIQQQIHHHHHH", data, 16, 2, 62, 1, 0, 64, 0, 0, 64, 56, 1, 0, 0, 0)
    struct.pack_into("<IIQQQQQQ", data, 64, 1, 5, 0, 0, 0, len(data), len(data), 4096)
    data[120:] = payload
    return bytes(data)
