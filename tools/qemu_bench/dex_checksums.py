#!/usr/bin/env python3
"""DEX header checksums and 4-byte-aligned stored JAR output (stdlib only)."""
import hashlib
import struct
import zipfile
import zlib


def finalize_dex(data):
    data = bytearray(data)
    if len(data) < 112 or not data.startswith(b'dex\n'):
        raise ValueError('Expected a standard DEX header')
    # signature excludes magic/checksum/signature; checksum includes NEW signature.
    data[12:32] = hashlib.sha1(data[32:]).digest()
    struct.pack_into('<I', data, 8, zlib.adler32(data[12:]) & 0xFFFFFFFF)
    return bytes(data)


def verify_dex(data):
    return (len(data) >= 112 and data.startswith(b'dex\n')
            and data[12:32] == hashlib.sha1(data[32:]).digest()
            and struct.unpack_from('<I', data, 8)[0] == zlib.adler32(data[12:]) & 0xFFFFFFFF)


def write_aligned_jar(path, entries):
    with zipfile.ZipFile(path, 'w', zipfile.ZIP_STORED) as jar:
        for name, data in entries.items():
            zi = zipfile.ZipInfo(name, date_time=(2009, 1, 1, 0, 0, 0))
            zi.external_attr = 0o644 << 16
            start = jar.fp.tell() + 30 + len(name.encode('utf-8'))
            padding = (-start) % 4
            if padding:
                # Valid private ZIP extra field (header itself is four bytes).
                zi.extra = struct.pack('<HH', 0xFFFF, padding) + bytes(padding)
            jar.writestr(zi, data)
    with zipfile.ZipFile(path) as jar:
        for entry in jar.infolist():
            with open(path, 'rb') as f:
                f.seek(entry.header_offset + 26)
                name_len, extra_len = struct.unpack('<HH', f.read(4))
            assert (entry.header_offset + 30 + name_len + extra_len) % 4 == 0
            if entry.filename.endswith('.dex'):
                assert verify_dex(jar.read(entry)), entry.filename
