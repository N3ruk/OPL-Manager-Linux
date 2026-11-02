import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from pathlib import Path
import tempfile,time,unittest
from unittest.mock import patch
from PyQt6.QtWidgets import QApplication,QMessageBox,QPushButton
from PyQt6.QtCore import Qt
from PyQt6.QtTest import QTest
from opl_manager import ui
from opl_manager.cfg_ui import CfgEditor
from opl_manager.art_ui import ArtDialog
from opl_manager.art import parse_catalog
from opl_manager.core import inspect_game
from test_core import make_iso
from test_art import XML,picture
import xml.etree.ElementTree as ET
app=QApplication.instance() or QApplication([])

class NewUiTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);make_iso(self.root/'DVD/a.iso');self.config=patch.object(ui,'CONFIG',self.root/'settings.json');self.config.start();self.w=ui.MainWindow();self.w.show();app.processEvents()
    def tearDown(self):
        if self.w.worker:self.w.worker.cancel.set();self.wait(self.w)
        self.w.close();app.processEvents();self.config.stop();self.tmp.cleanup()
    def wait(self,obj):
        deadline=time.monotonic()+8
        while getattr(obj,'worker',None) and time.monotonic()<deadline:app.processEvents();QTest.qWait(10)
        self.assertIsNone(obj.worker)
    def load(self):
        with patch.object(QMessageBox,'question',return_value=QMessageBox.StandardButton.Yes):self.w.load(self.root)
        self.wait(self.w)
    def test_prompt_accept_and_removed_button(self):
        with patch.object(QMessageBox,'question',return_value=QMessageBox.StandardButton.Yes) as question:self.w.load(self.root)
        self.wait(self.w);question.assert_called_once();self.assertFalse(ui.missing_folders(self.root));self.assertEqual((self.root/'DVD/games.bin').stat().st_size,92);self.assertEqual((self.root/'CD/games.bin').read_bytes(),b'')
        self.assertFalse(any('Carpetas OPL' in b.text() for b in self.w.findChildren(QPushButton)))
    def test_prompt_no_does_not_create_but_indexes_existing_media(self):
        with patch.object(QMessageBox,'question',return_value=QMessageBox.StandardButton.No):self.w.load(self.root)
        self.wait(self.w);self.assertFalse((self.root/'CFG').exists());self.assertEqual((self.root/'DVD/games.bin').stat().st_size,92)
    def test_refresh_reindexes_both_media_even_with_filter(self):
        self.load();make_iso(self.root/'CD/b.iso','SLES_512.22');make_iso(self.root/'DVD/c.iso')
        self.w.search.setText('no match');QTest.mouseClick(self.w.refresh_btn,Qt.MouseButton.LeftButton);self.wait(self.w)
        self.assertEqual(self.w.table.rowCount(),0);self.assertEqual((self.root/'DVD/games.bin').stat().st_size,184);self.assertEqual((self.root/'CD/games.bin').stat().st_size,92)
    def test_startup_remembers_library_and_regenerates(self):
        self.load();make_iso(self.root/'DVD/b.iso');new=ui.MainWindow();new.show();QTest.qWait(220);app.processEvents();self.wait(new)
        self.assertEqual(len(new.games),2);self.assertEqual((self.root/'DVD/games.bin').stat().st_size,184);new.close()
    def test_direct_cd_selection_checks_whole_library(self):
        self.load();make_iso(self.root/'CD/b.iso');self.w.load(self.root/'CD');self.wait(self.w)
        self.assertEqual(self.w.root,self.root);self.assertEqual(len(self.w.games),2)
    def editor(self):return CfgEditor(inspect_game(self.root/'DVD/a.iso',self.root,{}),self.w)
    def test_cfg_controls_survive_tab_switch_raw_roundtrip_and_save(self):
        e=self.editor();e.controls['Title'].setText('Mi título');e.tabs.setCurrentIndex(1);self.assertEqual(e.doc.get('Title'),'Mi título')
        e.modes[0].setChecked(True);e.modes[5].setChecked(True);e.tabs.setCurrentIndex(5)
        self.assertIn('$Compatibility=33',e.editor.toPlainText());e.editor.appendPlainText('Unknown=preserved');e.tabs.setCurrentIndex(2)
        self.assertEqual(e.doc.get('Unknown'),'preserved');e.controls['$EnableGSM'].setChecked(True);e.controls['$GSMVMode'].setCurrentIndex(10);e.save()
        data=e.path.read_text();self.assertIn('Title=Mi título',data);self.assertIn('Modes=1+6',data);self.assertIn('Unknown=preserved',data);self.assertIn('$EnableGSM=1',data)
    def test_cfg_existing_unknown_value_backup_and_external_conflict(self):
        game=inspect_game(self.root/'DVD/a.iso',self.root,{});game.cfg_path.parent.mkdir();before=b'# comment\r\nTitle=Old\r\nAspect=custom/value\r\nUnknown=kept\r\n';game.cfg_path.write_bytes(before)
        e=CfgEditor(game,self.w);e.controls['Title'].setText('New');e.save();self.assertEqual(game.cfg_path.with_suffix('.cfg.bak').read_bytes(),before);self.assertIn('Aspect=custom/value',game.cfg_path.read_text())
        e=CfgEditor(game,self.w);game.cfg_path.write_text('external');e.controls['Title'].setText('mine')
        with patch.object(QMessageBox,'warning') as warning:e.save();warning.assert_called_once()
        self.assertEqual(game.cfg_path.read_text(),'external');e.dirty=False;e.close()
    def test_cfg_validation_prevents_partial_write(self):
        e=self.editor();e.controls['Description'].setText('x'*256)
        with patch.object(QMessageBox,'warning') as warning:e.save();warning.assert_called_once()
        self.assertFalse(e.path.exists());e.dirty=False;e.close()
    def test_art_browser_variants_preview_then_publish_selected_type(self):
        game=inspect_game(self.root/'DVD/a.iso',self.root,{})
        with patch('opl_manager.art_ui.ArtClient.catalog',return_value=parse_catalog(ET.fromstring(XML))),patch('opl_manager.art_ui.fetch_image',return_value=picture()):
            d=ArtDialog(game,self.w);d.show();QTest.qWait(20);app.processEvents();self.wait(d)
            # The metadata worker starts a separate preview worker on completion.
            self.wait(d);self.assertFalse(game.art_path());d.kind.setCurrentIndex(d.kind.findData('SCR2'));app.processEvents();self.wait(d)
            self.assertEqual(d.variant.count(),2);d.variant.setCurrentIndex(1);app.processEvents();self.wait(d)
            QTest.mouseClick(d.save_btn,Qt.MouseButton.LeftButton);self.wait(d)
            self.assertTrue(game.art_path('SCR2'));self.assertFalse(game.art_path('COV'));d.close()
    def test_create_vmc_from_cfg_control(self):
        e=self.editor()
        with patch('opl_manager.cfg_ui.QInputDialog.getText',return_value=('testcard',True)),patch('opl_manager.cfg_ui.QInputDialog.getItem',return_value=('8',True)):e.new_vmc('$VMC_0')
        self.assertEqual((self.root/'VMC/testcard.bin').stat().st_size,8*1024*1024);e.save();self.assertIn('$VMC_0=testcard',e.path.read_text())
    def test_cfg_next_saves_before_navigation(self):
        e=self.editor();e.controls['Title'].setText('Saved before next')
        with patch.object(QMessageBox,'question',return_value=QMessageBox.StandardButton.Save):e.navigate(1)
        self.assertEqual(e.navigation,1);self.assertEqual(e.result(),3);self.assertIn('Title=Saved before next',e.path.read_text())
    def test_batch_cfg_button_action_and_no_overwrite(self):
        self.load()
        with patch.object(QMessageBox,'question',return_value=QMessageBox.StandardButton.Yes):self.w.batch_cfg()
        self.wait(self.w);g=self.w.games[0];self.assertTrue(g.cfg_path.exists())
        g.cfg_path.write_text('Title=My title\nUnknown=keep\n')
        with patch.object(QMessageBox,'question',return_value=QMessageBox.StandardButton.Yes):self.w.batch_cfg()
        self.wait(self.w);self.assertEqual(g.cfg_path.read_text(),'Title=My title\nUnknown=keep\n')
    def test_batch_rename_refreshes_cache_with_actual_new_filename(self):
        self.load()
        with patch.object(QMessageBox,'question',return_value=QMessageBox.StandardButton.Yes):self.w.batch_rename()
        self.wait(self.w)
        path=self.root/'DVD/Viewtiful Joe.iso';self.assertTrue(path.exists());row=(self.root/'DVD/games.bin').read_bytes()
        self.assertEqual(row[:65].rstrip(b'\0'),b'Viewtiful Joe')
