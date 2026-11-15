#!/usr/bin/env python3
"""Inspect standard AVB0 vbmeta (big endian), optionally through an AVBf footer."""
import argparse
import hashlib
from pathlib import Path
import struct


def inspect(data):
    if len(data) >= 64 and data[-64:-60] == b'AVBf':
        offset, size = struct.unpack_from('>QQ', data, len(data) - 44)
        data = data[offset:offset + size]
    if len(data) < 256 or data[:4] != b'AVB0':
        raise ValueError('Expected a 256-byte AVB0 header')
    u32 = lambda off: struct.unpack_from('>I', data, off)[0]
    u64 = lambda off: struct.unpack_from('>Q', data, off)[0]
    auth, aux, algorithm = u64(12), u64(20), u32(28)
    aux_start = 256 + auth
    if aux_start + aux > len(data):
        raise ValueError('Truncated authentication/auxiliary blocks')
    print(f'libavb {u32(4)}.{u32(8)}, algorithm={algorithm}, auth={auth}, aux={aux}')
    print(f'flags @120 (big endian)={u32(120):#x}, rollback={u64(112)}')
    print('release:', data[128:176].split(b'\0')[0].decode())
    if algorithm in range(1, 7):
        digest = hashlib.new('sha256' if algorithm <= 3 else 'sha512',
                             data[:256] + data[aux_start:aux_start + aux]).digest()
        stored = data[256 + u64(32):256 + u64(32) + u64(40)]
        print('header+aux digest MATCH:', digest == stored)
    pos, end = aux_start + u64(96), aux_start + u64(96) + u64(104)
    if end > aux_start + aux:
        raise ValueError('Descriptors outside auxiliary block')
    while pos < end:
        if pos + 16 > end:
            raise ValueError('Truncated descriptor header')
        tag, following = struct.unpack_from('>QQ', data, pos)
        size = 16 + following
        if size % 8 or pos + size > end:
            raise ValueError('Invalid descriptor size')
        d = data[pos:pos + size]
        print(f'@{pos}: tag={tag}, bytes={size}', end='')
        if tag == 1:
            values = struct.unpack_from('>IQQQIIIQQ32sIIII', d, 16)
            version, image, tree_off, tree_size, db, hb, roots, fec_off, fec_size, alg, pn, sl, dl, flags = values
            name = d[180:180 + pn].decode()
            print(f' HASHTREE {name}: image={image}, tree={tree_off}+{tree_size}, '
                  f'FEC roots={roots} offset={fec_off} size={fec_size}, flags={flags}')
        elif tag == 2:
            pn = struct.unpack_from('>I', d, 56)[0]
            print(' HASH', d[132:132 + pn].decode())
        elif tag == 4:
            pn = struct.unpack_from('>I', d, 20)[0]
            print(' CHAIN', d[92:92 + pn].decode())
        else:
            print()
        pos += size


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('image', type=Path)
    args = parser.parse_args()
    inspect(args.image.read_bytes())
