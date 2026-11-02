import io,xml.etree.ElementTree as ET,tempfile,unittest,threading
from pathlib import Path
from unittest.mock import patch
from PIL import Image
from opl_manager import art
from opl_manager.core import Game,ART_TYPES,Cancelled

XML='''<Envelope><ArtSearchSingleResult><COV>http://static2.oplmanager.com/cov.png</COV><ICO/><SCR><string>https://static2.oplmanager.com/1.png</string><string>http://static2.oplmanager.com/2.png</string></SCR><BG><string>https://static2.oplmanager.com/bg.png</string></BG></ArtSearchSingleResult></Envelope>'''
def picture():
    out=io.BytesIO();Image.new('RGB',(640,480),'blue').save(out,'PNG');return out.getvalue()

class ArtTests(unittest.TestCase):
    def test_parses_lists_and_uses_https(self):
        c=art.parse_catalog(ET.fromstring(XML));self.assertTrue(c['COV'][0].startswith('https://'));self.assertEqual(len(c['SCR']),2);self.assertEqual(c['SCR2'],c['SCR']);self.assertEqual(c['ICO'],[])
    def test_rejects_empty_response_and_untrusted_url(self):
        with self.assertRaises(ValueError):art.parse_catalog(ET.fromstring('<Envelope/>'))
        for url in ['file:///etc/passwd','https://evil.example/a.png','https://static2.oplmanager.com.evil.com/a','https://user:pass@static2.oplmanager.com/a','https://static2.oplmanager.com:123/a']:
            with self.assertRaises(ValueError):art.safe_art_url(url)
    def test_handshake_then_search_without_private_system_data(self):
        client=art.ArtClient()
        with patch.object(client,'soap',side_effect=[ET.fromstring('<r><userID>anonymous</userID></r>'),ET.fromstring(XML)]) as soap:
            client.catalog(Game(Path('/no.iso'),Path('/'),'Game','SLUS_209.46'))
        self.assertEqual(soap.call_args_list[0].args[:2],('ServiceStatus',{'userID':'NEW','versionid':37}))
        self.assertEqual(soap.call_args_list[1].args[1]['gameId'],'SLUS_209.46')
    def test_all_art_dimensions_palette_and_existing_backup(self):
        with tempfile.TemporaryDirectory() as td:
            g=Game(Path(td)/'g.iso',Path(td),'G','SLUS_209.46')
            for kind,size in ART_TYPES.items():
                dest=art.save_art_bytes(g,picture(),kind)
                with Image.open(dest) as image:self.assertEqual(image.size,size);self.assertEqual(image.mode,'P')
                with self.assertRaises(FileExistsError):art.save_art_bytes(g,picture(),kind)
                previous=dest.read_bytes();art.save_art_bytes(g,picture(),kind,True);self.assertEqual(dest.with_suffix('.png.bak').read_bytes(),previous)
            self.assertEqual(ART_TYPES['LAB'],(18,240));self.assertEqual(ART_TYPES['COV2'],(242,344))
    def test_batch_distinct_screens_missing_types_and_skip_existing(self):
        with tempfile.TemporaryDirectory() as td:
            g=Game(Path(td)/'g.iso',Path(td),'G','SLUS_209.46');client=art.ArtClient()
            with patch.object(client,'catalog',return_value=art.parse_catalog(ET.fromstring(XML))),patch.object(art,'fetch_image',return_value=picture()) as fetch:
                saved,missing,errors=art.download_art_batch([g],['COV','SCR','SCR2','ICO'],client=client)
                self.assertEqual((saved,missing,errors),(3,1,[]));self.assertEqual(fetch.call_args_list[1].args[0],'https://static2.oplmanager.com/1.png');self.assertEqual(fetch.call_args_list[2].args[0],'https://static2.oplmanager.com/2.png')
                saved,missing,errors=art.download_art_batch([g],['COV','SCR','SCR2'],client=client);self.assertEqual(saved,0)
    def test_bad_image_and_cancel_do_not_write(self):
        with tempfile.TemporaryDirectory() as td:
            g=Game(Path(td)/'g.iso',Path(td),'G','SLUS_209.46')
            with self.assertRaises(Exception):art.save_art_bytes(g,b'<html>no image</html>','COV')
            self.assertFalse(g.art_path());c=threading.Event();c.set()
            with self.assertRaises(Cancelled):art.download_art_batch([g],['COV'],cancel=c)
