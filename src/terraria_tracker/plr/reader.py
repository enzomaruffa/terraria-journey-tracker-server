"""Reader for the .NET ``BinaryWriter`` primitives Terraria saves with."""

import struct


class BinaryReadError(ValueError):
    pass


class BinaryReader:
    __slots__ = ("buffer", "offset")

    def __init__(self, buffer: bytes, offset: int = 0) -> None:
        self.buffer = buffer
        self.offset = offset

    @property
    def remaining(self) -> int:
        return len(self.buffer) - self.offset

    def read(self, count: int) -> bytes:
        end = self.offset + count
        if end > len(self.buffer):
            raise BinaryReadError(f"wanted {count} bytes at {self.offset}, only {self.remaining} left")
        chunk = self.buffer[self.offset : end]
        self.offset = end
        return chunk

    def skip(self, count: int) -> None:
        self.offset += count

    def read_uint8(self) -> int:
        return self.read(1)[0]

    def read_bool(self) -> bool:
        return self.read_uint8() != 0

    def read_int32(self) -> int:
        return struct.unpack("<i", self.read(4))[0]

    def read_uint32(self) -> int:
        return struct.unpack("<I", self.read(4))[0]

    def read_uint64(self) -> int:
        return struct.unpack("<Q", self.read(8))[0]

    def read_7bit_encoded_int(self) -> int:
        """Read the LEB128-style length prefix .NET writes before every string.

        The old parser assumed a single length byte, which silently truncates any string
        of 128 characters or more.
        """
        value = 0
        shift = 0
        while True:
            if shift > 28:
                raise BinaryReadError(f"malformed 7-bit encoded int at {self.offset}")
            byte = self.read_uint8()
            value |= (byte & 0x7F) << shift
            if not byte & 0x80:
                return value
            shift += 7

    def read_string(self) -> str:
        length = self.read_7bit_encoded_int()
        raw = self.read(length)
        try:
            return raw.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise BinaryReadError(f"string at {self.offset - length} is not valid UTF-8") from exc
