from pathlib import Path
import tempfile,threading,unittest
from unittest.mock import patch
from opl_manager.library import library_root,missing_folders,create_folders,refresh_library
from opl_manager.core import Cancelled
from test_core import make_iso

class LibraryAutoTests(unittest.TestCase):
    def setUp(self):self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
    def tearDown(self):self.tmp.cleanup()
    def test_case_insensitive_preparation(self):
        (self.root/'dvd').mkdir();create_folders(self.root)
        self.assertFalse(missing_folders(self.root));self.assertFalse((self.root/'DVD').exists())
        self.assertEqual(library_root(self.root/'dvd'),self.root)
    def test_conflicting_name_creates_nothing(self):
        (self.root/'CFG').write_text('keep')
        with self.assertRaises(ValueError):create_folders(self.root)
        self.assertFalse((self.root/'DVD').exists());self.assertEqual((self.root/'CFG').read_text(),'keep')
    def test_updates_both_media_and_empty_stale(self):
        make_iso(self.root/'DVD/dvd.iso');make_iso(self.root/'CD/cd.iso');create_folders(self.root)
        games,w,result,error=refresh_library(self.root);self.assertFalse(error);self.assertEqual(result.count,2)
        self.assertEqual((self.root/'DVD/games.bin').stat().st_size,92);self.assertEqual((self.root/'CD/games.bin').stat().st_size,92)
        (self.root/'CD/cd.iso').unlink();refresh_library(self.root)
        self.assertEqual((self.root/'CD/games.bin').read_bytes(),b'')
    def test_no_rewrite_or_second_scan_when_unchanged(self):
        p=make_iso(self.root/'DVD/a.iso');create_folders(self.root);refresh_library(self.root)
        before=p.stat();index=self.root/'DVD/games.bin';mtime=index.stat().st_mtime_ns
        with patch('opl_manager.games_index.scan_library',side_effect=AssertionError('double scan')):refresh_library(self.root)
        self.assertEqual(index.stat().st_mtime_ns,mtime);self.assertEqual(p.stat().st_mtime_ns,before.st_mtime_ns)
    def test_bad_disc_still_displays_library_no_incomplete_cache(self):
        p=self.root/'DVD/bad.iso';p.parent.mkdir();p.write_bytes(b'bad');(p.parent/'games.bin').write_bytes(b'old')
        games,w,result,error=refresh_library(self.root)
        self.assertEqual(len(games),1);self.assertIsNone(result);self.assertIn('SYSTEM.CNF',error);self.assertEqual((p.parent/'games.bin').read_bytes(),b'old')
    def test_cancel_does_not_publish(self):
        make_iso(self.root/'DVD/a.iso');cancel=threading.Event();cancel.set()
        with self.assertRaises(Cancelled):refresh_library(self.root,cancel=cancel)
        self.assertFalse((self.root/'DVD/games.bin').exists())
    def test_no_media_does_not_create_structure(self):
        make_iso(self.root/'a.iso');games,w,result,error=refresh_library(self.root)
        self.assertEqual(len(games),1);self.assertIsNone(result);self.assertFalse(error);self.assertTrue(missing_folders(self.root))
