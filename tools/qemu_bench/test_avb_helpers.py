#!/usr/bin/env python3
"""Offline regression tests; no disk image is modified."""
import contextlib
import io
import struct
import tempfile
import unittest
import zipfile

from dex_checksums import finalize_dex, verify_dex, write_aligned_jar

from dump_vbmeta import inspect
from system_port import crc32c


class AvbTests(unittest.TestCase):
    def header(self):
        data = bytearray(256)
        data[:4] = b'AVB0'
        struct.pack_into('>I', data, 4, 1)
        struct.pack_into('>I', data, 120, 3)
        return data

    def test_header_flags_big_endian(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            inspect(self.header())
        self.assertIn('flags @120 (big endian)=0x3', out.getvalue())

    def test_footer_resolves_vbmeta(self):
        footer = struct.pack('>4sIIQQQ28x', b'AVBf', 1, 0, 4096, 4096, 256)
        with contextlib.redirect_stdout(io.StringIO()):
            inspect(bytes(4096) + self.header() + footer)

    def test_reject_invalid_header(self):
        with self.assertRaises(ValueError):
            inspect(b'AVBf' + bytes(252))

    def test_reject_truncated_auxiliary(self):
        data = self.header()
        struct.pack_into('>Q', data, 20, 64)
        with self.assertRaises(ValueError):
            inspect(data)

    def test_dex_signature_before_checksum(self):
        data = b'dex\n039\0' + bytes(104) + b'test payload'
        fixed = finalize_dex(data)
        self.assertTrue(verify_dex(fixed))
        self.assertFalse(verify_dex(fixed[:-1] + b'X'))
        self.assertEqual(finalize_dex(fixed), fixed)

    def test_aligned_jar_roundtrip(self):
        data = finalize_dex(b'dex\n039\0' + bytes(104))
        with tempfile.TemporaryDirectory() as tmp:
            path = tmp + '/test.jar'
            write_aligned_jar(path, {'a': b'x', 'classes.dex': data})
            with zipfile.ZipFile(path) as jar:
                self.assertEqual(jar.read('classes.dex'), data)
                self.assertIsNone(jar.testzip())

    def test_erofs_crc_has_no_final_xor(self):
        self.assertEqual(crc32c(b'123456789'), 0x1CF96D7C)
        self.assertEqual(crc32c(b''), 0xFFFFFFFF)


if __name__ == '__main__':
    unittest.main()
