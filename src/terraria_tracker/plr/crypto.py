"""Terraria encrypts character files with AES-128-CBC under a fixed, shipped key.

The key doubles as the IV, and is the UTF-16LE encoding of the string below — the same
constant Terraria itself uses, so this is obfuscation rather than protection.
"""

from Crypto.Cipher import AES

_PASSPHRASE = "h3y_gUyZ"
KEY = _PASSPHRASE.encode("utf-16-le")
BLOCK_SIZE = AES.block_size


class DecryptionError(ValueError):
    pass


def decrypt_player_file(raw: bytes) -> bytes:
    """Decrypt a .plr file in memory.

    The previous implementation shelled out through temporary files on disk, which raced
    against Terraria's own writes and left `tmp`/`tmp-out` droppings in the working
    directory.
    """
    if not raw:
        raise DecryptionError("character file is empty")
    if len(raw) % BLOCK_SIZE:
        raise DecryptionError(
            f"character file is {len(raw)} bytes, which is not a multiple of the {BLOCK_SIZE}-byte AES block "
            "size — it is probably truncated or not a .plr file"
        )

    cipher = AES.new(KEY, AES.MODE_CBC, KEY)
    return cipher.decrypt(raw)


def encrypt_player_file(plain: bytes) -> bytes:
    """Inverse of :func:`decrypt_player_file`, used by the test fixtures."""
    padding = -len(plain) % BLOCK_SIZE
    cipher = AES.new(KEY, AES.MODE_CBC, KEY)
    return cipher.encrypt(plain + bytes([padding or BLOCK_SIZE]) * (padding or BLOCK_SIZE))
