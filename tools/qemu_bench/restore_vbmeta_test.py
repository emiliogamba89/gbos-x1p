#!/usr/bin/env python3
"""Restore only GPT vbmeta_a/b from recovery, with optional standard AVB flags.
Backs up both current and official partitions; never touches super or userdata.
"""
import argparse
import datetime
import hashlib
from pathlib import Path
import os
import struct
import subprocess


def partitions(f):
    f.seek(512)
    h = f.read(92)
    assert h[:8] == b'EFI PART'
    lba, count, size = struct.unpack_from('<QII', h, 72)
    assert 0 < count <= 4096 and 128 <= size <= 4096
    f.seek(lba * 512)
    entries = f.read(count * size)
    result = {}
    for i in range(count):
        e = entries[i * size:(i + 1) * size]
        name = e[56:128].decode('utf-16-le').rstrip('\0')
        if name in ('vbmeta_a', 'vbmeta_b'):
            first, last = struct.unpack_from('<QQ', e, 32)
            result[name] = (first * 512, (last - first + 1) * 512)
    assert set(result) == {'vbmeta_a', 'vbmeta_b'}
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('disk', type=Path)
    p.add_argument('recovery', type=Path)
    p.add_argument('--flags', type=int, choices=range(4), default=0)
    p.add_argument('--apply', action='store_true')
    args = p.parse_args()
    assert args.disk.resolve() != args.recovery.resolve()
    processes = subprocess.check_output(['ps', '-eo', 'args='], text=True)
    if any(line.lstrip().startswith(('qemu-system-', '/usr/bin/qemu-system-')) for line in processes.splitlines()):
        raise SystemExit('Stop QEMU before running this tool')
    with args.disk.open('rb') as disk, args.recovery.open('rb') as recovery:
        dst, src = partitions(disk), partitions(recovery)
        assert dst == src, 'Recovery and target GPT vbmeta layout differ'
        plan = []
        for name, (offset, size) in dst.items():
            assert size <= 16 * 1024 * 1024
            recovery.seek(offset)
            official = recovery.read(size)
            assert len(official) == size and official[:4] == b'AVB0'
            modified = bytearray(official)
            struct.pack_into('>I', modified, 120, args.flags)
            disk.seek(offset)
            before = disk.read(size)
            assert len(before) == size
            plan.append((name, offset, before, official, bytes(modified)))
            print(f'{name}: offset={offset}, size={size}, flags={args.flags}, official sha256={hashlib.sha256(official).hexdigest()}')
    if not args.apply:
        print('Dry run; use --apply to back up and write')
        return
    backup = Path('/home/zero89/avb-backups') / datetime.datetime.now().strftime('%Y%m%d-%H%M%S-%f')
    backup.mkdir(parents=True)
    for name, offset, before, official, modified in plan:
        for suffix, blob in [('before', before), ('official', official), ('test', modified)]:
            with (backup / f'{name}.{suffix}.bin').open('xb') as f:
                f.write(blob)
                f.flush()
                os.fsync(f.fileno())
    print('Backup:', backup, flush=True)
    with args.disk.open('r+b') as disk:
        for name, offset, before, official, modified in plan:
            disk.seek(offset)
            disk.write(modified)
        disk.flush()
        os.fsync(disk.fileno())
        for name, offset, before, official, modified in plan:
            disk.seek(offset)
            assert disk.read(len(modified)) == modified
            print(name, 'read-back OK')


if __name__ == '__main__':
    main()
