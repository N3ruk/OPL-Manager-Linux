from pathlib import Path
import tempfile,unittest
from opl_manager.cfg import CfgDocument,update_cfg_titles
from opl_manager.core import inspect_game
from test_core import make_iso

class CfgTests(unittest.TestCase):
    def test_preserves_unknown_comments_order_and_equals(self):
        doc=CfgDocument('# header\nUnknown=A=B\nTitle=Old\n; comment\n')
        doc.set('Title','New');self.assertEqual(doc.text(),'# header\nUnknown=A=B\nTitle=New\n; comment\n')
    def test_mode_bits_and_companion(self):
        doc=CfgDocument();doc.set_modes([0,2,7]);self.assertEqual(doc.compatibility(),133);self.assertEqual(doc.get('Modes'),'1+3+8')
        doc.set_modes([]);self.assertNotIn('$Compatibility',doc.text());self.assertNotIn('Modes=',doc.text())
    def test_duplicate_only_changed_key_and_remove(self):
        doc=CfgDocument('Title=one\nUnknown=1\nTitle=two\n');doc.set('Title','three')
        self.assertEqual(doc.text(),'Title=three\nUnknown=1\n');doc.set('Title','');self.assertEqual(doc.text(),'Unknown=1\n')
    def test_newline_and_nul_rejected(self):
        for value in ['one\ntwo','\x00','\r']:
            with self.assertRaises(ValueError):CfgDocument().set('Title',value)
    def test_batch_fills_only_missing_and_keeps_settings(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);g=inspect_game(make_iso(root/'DVD/a.iso'),root,{})
            g.cfg_path.parent.mkdir();g.cfg_path.write_text('$Compatibility=65\nUnknown=kept\n')
            self.assertEqual(update_cfg_titles([g])[0],1);self.assertIn('Unknown=kept',g.cfg_path.read_text());self.assertIn('$Compatibility=65',g.cfg_path.read_text())
            self.assertEqual(update_cfg_titles([g])[0],0);self.assertTrue(g.cfg_path.with_suffix('.cfg.bak').exists())
