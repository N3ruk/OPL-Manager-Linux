from pathlib import Path
import hashlib,struct,tempfile,threading,unittest,zlib
from opl_manager.vmc import create_vmc
from opl_manager.operations import game_hashes
from opl_manager.core import Game,Cancelled

class VmcOperationTests(unittest.TestCase):
    def test_formatted_card_superblock_fat_and_root(self):
        with tempfile.TemporaryDirectory() as td:
            path=Path(td)/'card.bin';create_vmc(path)
            data=path.read_bytes();self.assertEqual(len(data),8*1024*1024)
            golden=(Path(__file__).parent/'fixtures/vmc-superblock-8mb.bin').read_bytes();self.assertEqual(data[:1024],golden)
            alloc=struct.unpack_from('<I',data,52)[0];self.assertEqual(alloc,41)
            self.assertEqual(data[alloc*1024+64:alloc*1024+66],b'.\0');self.assertEqual(data[alloc*1024+512+64:alloc*1024+512+67],b'..\0')
            self.assertEqual(struct.unpack_from('<I',data,9*1024)[0],0xffffffff);self.assertEqual(struct.unpack_from('<I',data,9*1024+4)[0],0x7fffffff)
            with self.assertRaises(FileExistsError):create_vmc(path)
    def test_cancelled_card_not_published_and_size_validation(self):
        with tempfile.TemporaryDirectory() as td:
            path=Path(td)/'card.bin';cancel=threading.Event();cancel.set()
            with self.assertRaises(Cancelled):create_vmc(path,cancel=cancel)
            self.assertFalse(path.exists());self.assertEqual(list(path.parent.iterdir()),[])
            with self.assertRaises(ValueError):create_vmc(path,7)
    def test_hashes_match_independent_algorithms(self):
        with tempfile.TemporaryDirectory() as td:
            path=Path(td)/'data';data=b'OPL\x00\x10'*1500000;path.write_bytes(data)
            result=game_hashes(Game(path,path.parent,'Test'))
            self.assertEqual(result['CRC32'],f'{zlib.crc32(data):08X}')
            for name in ('md5','sha1','sha256'):self.assertEqual(result[name.upper()],hashlib.new(name,data).hexdigest())
    def test_64mb_unused_fat_cluster_stays_erased(self):
        with tempfile.TemporaryDirectory() as td:
            path=Path(td)/'card.bin';create_vmc(path,64)
            self.assertEqual(path.stat().st_size,64*1024*1024)
            with path.open('rb') as f:
                header=f.read(384);alloc=struct.unpack_from('<I',header,52)[0];self.assertEqual(alloc,265)
                f.seek((alloc-1)*1024);self.assertEqual(f.read(1024),b'\xff'*1024)
