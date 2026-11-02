from pathlib import Path
import struct
import tempfile
import threading
import unittest
from unittest.mock import patch
from opl_manager import core as c
from opl_manager import games_index as idx
from test_core import make_iso


class IndexTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def image(self, name='DVD/game.iso', gid='SLES_526.78'):
        return make_iso(self.root / name, gid)

    def unpack(self, path, size=64):
        return list(idx.record_struct(size).iter_unpack(path.read_bytes()))

    def test_windows_golden_record_byte_exact(self):
        path = self.image('DVD/SLES_534.81.10000 Bullets.iso', 'SLES_534.81')
        with path.open('r+b') as stream:
            stream.truncate(2134 << 20)
        game = c.inspect_game(path, self.root, {})
        expected = (Path(__file__).parent / 'fixtures/games-windows-first-record.bin').read_bytes()
        self.assertEqual(idx.encode_game(game), expected)

    def test_modern_filename_not_database_title(self):
        path = self.image('DVD/My filename.ISO')
        result = idx.generate_indexes(self.root)
        row = self.unpack(path.parent / 'games.bin')[0]
        self.assertEqual(result.count, 1)
        self.assertEqual(row[0].rstrip(b'\0'), b'My filename')
        self.assertEqual(row[1].rstrip(b'\0'), b'SLES_526.78')
        self.assertEqual(row[2].rstrip(b'\0'), b'.ISO')
        self.assertEqual(row[3:6], (1, 0x14, 2))
        self.assertEqual(path.with_name(row[0].rstrip(b'\0').decode() + row[2].rstrip(b'\0').decode()), path)

    def test_dvd_cd_separation_empty_and_lowercase(self):
        self.image('dvd/movie.iso')
        self.image('cd/disc.iso')
        result = idx.generate_indexes(self.root)
        self.assertEqual(result.count, 2)
        self.assertEqual(self.unpack(self.root / 'cd/games.bin')[0][4], 0x12)
        self.assertEqual(self.unpack(self.root / 'dvd/games.bin')[0][4], 0x14)
        (self.root / 'cd/disc.iso').unlink()
        idx.generate_indexes(self.root)
        self.assertEqual((self.root / 'cd/games.bin').read_bytes(), b'')

    def test_selected_cd_does_not_modify_sibling_dvd(self):
        self.image('CD/game.iso')
        self.image('DVD/game.iso')
        sibling = self.root / 'DVD/games.bin'
        sibling.write_bytes(b'KEEP')
        result = idx.generate_indexes(self.root / 'CD')
        self.assertEqual(result.count, 1)
        self.assertEqual(sibling.read_bytes(), b'KEEP')

    def test_recent_160_byte_profile_and_offsets(self):
        path = self.image('DVD/' + 'x' * 100 + '.iso')
        result = idx.generate_indexes(self.root, 160)
        data = (path.parent / 'games.bin').read_bytes()
        self.assertEqual(len(data), 188)
        self.assertEqual(data[161:174], b'SLES_526.78\0\0')
        self.assertEqual(data[174:179], b'.iso\0')
        self.assertEqual(data[179:184], b'\x01\x14\x02\0\0')
        self.assertEqual(result.name_bytes, 160)

    def test_long_utf8_name_aborts_without_truncation_or_partial_publication(self):
        self.image('DVD/good.iso')
        self.image('CD/' + 'é' * 33 + '.iso')
        old = self.root / 'DVD/games.bin'
        old.write_bytes(b'KEEP')
        with self.assertRaisesRegex(ValueError, '66 bytes'):
            idx.generate_indexes(self.root)
        self.assertEqual(old.read_bytes(), b'KEEP')
        self.assertFalse((self.root / 'CD/games.bin').exists())

    def test_unidentified_image_aborts_before_writing(self):
        self.image()
        (self.root / 'DVD/bad.iso').write_bytes(b'not ISO')
        with self.assertRaisesRegex(ValueError, 'SYSTEM.CNF'):
            idx.generate_indexes(self.root)
        self.assertFalse((self.root / 'DVD/games.bin').exists())

    def test_mismatched_classic_id_not_cached(self):
        self.image('DVD/SLUS_209.46.Wrong.iso')
        with self.assertRaisesRegex(ValueError, 'ID del disco'):
            idx.generate_indexes(self.root)

    def test_cancel_keeps_old_index_and_images_unchanged(self):
        path = self.image()
        before = (path.read_bytes(), path.stat().st_mtime_ns)
        old = path.parent / 'games.bin'
        old.write_bytes(b'KEEP')
        event = threading.Event()
        event.set()
        with self.assertRaises(c.Cancelled):
            idx.generate_indexes(self.root, cancel=event)
        self.assertEqual(old.read_bytes(), b'KEEP')
        idx.generate_indexes(self.root)
        self.assertEqual((path.read_bytes(), path.stat().st_mtime_ns), before)

    def test_zso_and_vcd_exclusion(self):
        path = self.image()
        zso = path.with_suffix('.zso')
        c.convert_image(path, zso)
        (path.parent / 'SCES_000.01.PS1.vcd').write_bytes(b'VCD')
        result = idx.generate_indexes(self.root)
        rows = self.unpack(path.parent / 'games.bin')
        self.assertEqual(result.count, 2)
        self.assertEqual({r[2].rstrip(b'\0') for r in rows}, {b'.iso', b'.zso'})

    def test_loose_images_not_moved_or_indexed(self):
        path = self.image('game.iso')
        with self.assertRaisesRegex(ValueError, 'DVD/CD'):
            idx.generate_indexes(self.root)
        self.assertTrue(path.exists())
        self.assertFalse((self.root / 'games.bin').exists())

    def test_symlink_index_aborts_all_publication(self):
        self.image('DVD/game.iso')
        self.image('CD/game.iso')
        keep = self.root / 'keep'
        keep.write_bytes(b'KEEP')
        (self.root / 'CD/games.bin').symlink_to(keep)
        with self.assertRaises(ValueError):
            idx.generate_indexes(self.root)
        self.assertEqual(keep.read_bytes(), b'KEEP')
        self.assertFalse((self.root / 'DVD/games.bin').exists())

    def test_io_failure_reports_files_already_committed(self):
        self.image('DVD/game.iso')
        (self.root / 'CD').mkdir()
        real_write = c.atomic_bytes
        def fail_cd(path, data):
            if path.parent.name == 'CD':
                raise OSError('test failure')
            real_write(path, data)
        with patch.object(idx, 'atomic_bytes', side_effect=fail_cd):
            with self.assertRaisesRegex(OSError, 'DVD/games.bin'):
                idx.generate_indexes(self.root)
        self.assertEqual(len((self.root / 'DVD/games.bin').read_bytes()), 92)

    def test_unknown_layout_rejected(self):
        with self.assertRaises(ValueError):
            idx.generate_indexes(self.root, 128)


if __name__ == '__main__':
    unittest.main()
