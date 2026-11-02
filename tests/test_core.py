import csv
import hashlib
import io
import os
from pathlib import Path
import struct
import tempfile
import threading
import unittest
from unittest.mock import patch
from PIL import Image
from opl_manager import core as c


def record(extent,size,name):
    name=name if isinstance(name,bytes) else name.encode('ascii');length=33+len(name)+(len(name)%2==0);b=bytearray(length)
    b[0]=length;struct.pack_into('<I',b,2,extent);struct.pack_into('>I',b,6,extent);struct.pack_into('<I',b,10,size);struct.pack_into('>I',b,14,size);b[28:32]=b'\x01\0\0\x01';b[32]=len(name);b[33:33+len(name)]=name
    return b


def make_iso(path,gid='SLES_526.78',noise=False):
    b=bytearray(64*2048);pvd=memoryview(b)[16*2048:17*2048];pvd[0:7]=b'\x01CD001\x01';pvd[156:190]=record(20,2048,b'\0')
    cnf=f'BOOT2 = cdrom0:\\{gid};1\r\nVER = 1.00\r\n'.encode();r=record(21,len(cnf),'SYSTEM.CNF;1');b[20*2048:20*2048+len(r)]=r;b[21*2048:21*2048+len(cnf)]=cnf
    if noise:b[30*2048:31*2048]=os.urandom(2048)
    path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(b);return path


class CoreTests(unittest.TestCase):
    def setUp(self):self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
    def tearDown(self):self.tmp.cleanup()
    def game(self):
        p=make_iso(self.root/'DVD/game.iso');return c.inspect_game(p,self.root,c.game_database())
    def test_id_formats(self):
        for s in ['SLES_526.78','sles-52678','SLES 52678']:self.assertEqual(c.normalize_id(s),'SLES_526.78')
    def test_reject_path_as_id(self):
        with self.assertRaises(ValueError):c.require_id('../../SLES_526.78')
    def test_read_real_iso_structure(self):
        g=self.game();self.assertEqual(g.game_id,'SLES_526.78');self.assertEqual(g.title,'Viewtiful Joe');self.assertEqual(g.issues,[])
    def test_content_over_filename(self):
        p=make_iso(self.root/'SLUS_209.46.Wrong.iso');g=c.inspect_game(p,self.root,{})
        self.assertEqual(g.game_id,'SLES_526.78');self.assertTrue(g.issues)
    def test_corrupt_iso_visible(self):
        p=self.root/'bad.iso';p.write_bytes(b'bad');games,w=c.scan_library(self.root);self.assertEqual(len(games),1);self.assertTrue(games[0].issues)
    def test_malformed_root_bounded(self):
        p=make_iso(self.root/'bad.iso');b=bytearray(p.read_bytes());struct.pack_into('<I',b,16*2048+166,0xffffffff);p.write_bytes(b)
        with c.DiscImage(p) as im:
            with self.assertRaises(ValueError):c.iso_id(im)
    def test_scan_is_readonly_and_nonrecursive(self):
        self.game();make_iso(self.root/'sub/deep/ignored.iso');before={str(p):p.stat().st_mtime_ns for p in self.root.rglob('*') if p.is_file()}
        gs,w=c.scan_library(self.root);after={str(p):p.stat().st_mtime_ns for p in self.root.rglob('*') if p.is_file()}
        self.assertEqual(len(gs),1);self.assertEqual(before,after)
    def test_select_dvd_keeps_shared_art_root(self):
        g=self.game();gs,w=c.scan_library(self.root/'DVD');self.assertEqual(gs[0].root,self.root)
    def test_case_insensitive_directories(self):
        p=make_iso(self.root/'dvd/game.iso');gs,w=c.scan_library(self.root);self.assertEqual(len(gs),1)
    def test_vcd_catalog(self):
        (self.root/'SCES_000.01.Test.vcd').write_bytes(b'x');gs,w=c.scan_library(self.root);self.assertEqual(gs[0].kind,'VCD');self.assertEqual(gs[0].game_id,'SCES_000.01')
    def test_ul_layout_matches_opl(self):
        r=bytearray(64);r[:4]=b'Test';r[32:35]=b'ul.';r[35:46]=b'SLES_526.78';r[47]=2;r[48]=0x14
        (self.root/'ul.cfg').write_bytes(r);(self.root/'ul.12345678.SLES_526.78.00').write_bytes(b'abc');(self.root/'ul.12345678.SLES_526.78.01').write_bytes(b'defg')
        gs,w=c.scan_library(self.root);self.assertEqual(len(gs),1);g=gs[0];self.assertEqual(g.kind,'UL');self.assertEqual(g.size,7);self.assertFalse(g.issues);self.assertEqual(g.media,'DVD')
    def test_ul_ambiguous_parts_not_hashed(self):
        r=bytearray(64);r[:4]=b'Test';r[32:35]=b'ul.';r[35:46]=b'SLES_526.78';r[47]=1
        (self.root/'ul.cfg').write_bytes(r)
        for key in ('12345678','87654321'):(self.root/f'ul.{key}.SLES_526.78.00').write_bytes(b'a')
        gs,w=c.scan_library(self.root);self.assertTrue(gs[0].issues);self.assertEqual(gs[0].parts,[])
        with self.assertRaises(ValueError):c.hash_game(gs[0])
    def test_ul_missing_parts_warn(self):
        r=bytearray(64);r[32:35]=b'ul.';r[35:46]=b'SLES_526.78';r[47]=2;(self.root/'ul.cfg').write_bytes(r)
        gs,w=c.scan_library(self.root);self.assertTrue(gs[0].issues)
    def test_ul_partial_record_warn(self):
        (self.root/'ul.cfg').write_bytes(b'x');gs,w=c.scan_library(self.root);self.assertTrue(w)
    def test_rename_preserves_content(self):
        g=self.game();before=hashlib.sha256(g.path.read_bytes()).hexdigest();old=g.path;dest=c.rename_game(g,'Viewtiful Joe')
        self.assertEqual(dest.name,'SLES_526.78.Viewtiful Joe.iso');self.assertFalse(old.exists());self.assertEqual(hashlib.sha256(dest.read_bytes()).hexdigest(),before)
    def test_rename_collision_no_clobber(self):
        g=self.game();dest=g.path.with_name('SLES_526.78.Test.iso');dest.write_bytes(b'KEEP')
        with self.assertRaises(FileExistsError):c.rename_game(g,'Test')
        self.assertEqual(dest.read_bytes(),b'KEEP');self.assertTrue(g.path.exists())
    def test_rename_invalid(self):
        g=self.game()
        for name in ['../escape','a/b','a:b','', 'x'*33]:
            with self.assertRaises(ValueError):c.rename_game(g,name)
    def test_rename_exfat_fallback(self):
        g=self.game()
        with patch('opl_manager.core.os.link',side_effect=OSError(95,'unsupported')):dest=c.rename_game(g,'FAT test')
        self.assertTrue(dest.is_file());self.assertFalse(g.path.exists())
    def test_cfg_backup_and_crlf(self):
        p=self.root/'CFG/SLES_526.78.cfg';c.backup_text(p,'Title=First\n',None);old=p.read_bytes();c.backup_text(p,'Title=Second\nUnknown=Keep\n',old)
        self.assertEqual(p.with_suffix('.cfg.bak').read_bytes(),old);self.assertEqual(p.read_bytes(),b'Title=Second\r\nUnknown=Keep\r\n')
    def test_cfg_external_changes_not_overwritten(self):
        p=self.root/'config.cfg';p.write_bytes(b'new')
        with self.assertRaises(ValueError):c.backup_text(p,'mine',b'old')
        self.assertEqual(p.read_bytes(),b'new')
    def test_atomic_no_clobber_exfat(self):
        p=self.root/'art.png'
        with patch('opl_manager.core.os.link',side_effect=OSError(95,'unsupported')):c.atomic_bytes(p,b'hello',False)
        with self.assertRaises(FileExistsError):c.atomic_bytes(p,b'bye',False)
        self.assertEqual(p.read_bytes(),b'hello')
    def test_refuse_symlink_writes(self):
        target=self.root/'real';target.write_bytes(b'keep');p=self.root/'link';p.symlink_to(target)
        with self.assertRaises(ValueError):c.atomic_bytes(p,b'change')
        self.assertEqual(target.read_bytes(),b'keep')
    def test_import_art_dimensions(self):
        g=self.game();src=self.root/'photo.jpg';Image.new('RGB',(900,1200),'blue').save(src);dest=c.import_art(g,src)
        with Image.open(dest) as im:self.assertEqual(im.size,(140,200))
        self.assertEqual(g.art_path(),dest)
        with self.assertRaises(FileExistsError):c.import_art(g,src)
    def test_download_cover_validated(self):
        g=self.game();buf=io.BytesIO();Image.new('RGB',(140,200),'blue').save(buf,'JPEG');buf.seek(0)
        with patch('urllib.request.urlopen',return_value=buf):c.download_cover(g)
        self.assertTrue(g.art_path().exists())
    def test_download_rejects_html(self):
        g=self.game()
        with patch('urllib.request.urlopen',return_value=io.BytesIO(b'<html>not art</html>')):
            with self.assertRaises(Exception):c.download_cover(g)
        self.assertIsNone(g.art_path())
    def test_hash_matches_sha256(self):
        g=self.game();self.assertEqual(c.hash_game(g),hashlib.sha256(g.path.read_bytes()).hexdigest())
    def test_export_csv_and_formula_escaping(self):
        g=self.game();g.title='=CMD()';p=self.root/'out.csv';c.export_csv([g],p)
        rows=list(csv.reader(io.StringIO(p.read_text('utf-8-sig'))));self.assertEqual(rows[1][0],"'=CMD()");self.assertEqual(rows[1][1],g.game_id)
    def test_zso_roundtrip_compressed_and_raw(self):
        p=make_iso(self.root/'input.iso',noise=True);z=self.root/'out.zso';out=self.root/'roundtrip.iso';c.convert_image(p,z);c.convert_image(z,out)
        self.assertEqual(p.read_bytes(),out.read_bytes());self.assertLess(z.stat().st_size,p.stat().st_size)
        with c.DiscImage(z) as image:self.assertEqual(c.iso_id(image),'SLES_526.78')
    def test_zso_random_reads(self):
        p=make_iso(self.root/'a.iso',noise=True);z=self.root/'a.zso';c.convert_image(p,z);raw=p.read_bytes()
        with c.DiscImage(z) as image:
            for offset,n in [(13,4500),(0,0),(30*2048,2048),(len(raw)-31,31)]:self.assertEqual(image.read(offset,n),raw[offset:offset+n])
    def test_zso_malformed_index(self):
        p=self.root/'bad.zso';p.write_bytes(struct.pack('<4sIQIBB2x',b'ZISO',24,2048,2048,1,0)+struct.pack('<II',0,40)+b'x'*16)
        with c.DiscImage(p) as image:
            with self.assertRaises(ValueError):image.read(0,2048)
    def test_cancel_conversion_no_output(self):
        p=make_iso(self.root/'a.iso');event=threading.Event();event.set();dest=self.root/'a.zso'
        with self.assertRaises(c.Cancelled):c.convert_image(p,dest,cancel=event)
        self.assertFalse(dest.exists());self.assertEqual(list(self.root.glob('*.part')),[]);self.assertTrue(p.exists())
    def test_conversion_never_overwrites(self):
        p=make_iso(self.root/'a.iso');z=self.root/'a.zso';z.write_bytes(b'KEEP')
        with self.assertRaises(FileExistsError):c.convert_image(p,z)
        self.assertEqual(z.read_bytes(),b'KEEP')
    def test_cancel_scan(self):
        self.game();event=threading.Event();event.set()
        with self.assertRaises(c.Cancelled):c.scan_library(self.root,cancel=event)

if __name__=='__main__':unittest.main()
