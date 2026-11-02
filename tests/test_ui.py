import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch
from PyQt6.QtWidgets import QApplication,QDialog
from PyQt6.QtCore import Qt
from PyQt6.QtTest import QTest
from opl_manager import ui
from test_core import make_iso

app=QApplication.instance() or QApplication([])

class UiTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);make_iso(self.root/'DVD/joe.iso');make_iso(self.root/'DVD/rayman.iso','SLES_512.22')
        ui.create_folders(self.root)
        self.config=patch.object(ui,'CONFIG',self.root/'settings.json');self.config.start();self.w=ui.MainWindow();self.w.show();app.processEvents()
    def tearDown(self):
        if self.w.worker:self.w.worker.cancel.set();self.wait()
        self.w.close();app.processEvents();self.config.stop();self.tmp.cleanup()
    def wait(self):
        deadline=time.monotonic()+8
        while self.w.worker and time.monotonic()<deadline:app.processEvents();QTest.qWait(10)
        self.assertIsNone(self.w.worker)
    def load(self):self.w.load(self.root);self.wait()
    def test_async_scan_and_select(self):
        self.load();self.assertEqual(self.w.table.rowCount(),2);self.assertIsNotNone(self.w.current);self.assertEqual(self.w.stat_values[0].text(),'2');self.assertTrue(self.w.detail_buttons[0].isEnabled())
    def test_search_id_and_title(self):
        self.load();self.w.search.setText('rayman');app.processEvents();self.assertEqual(self.w.table.rowCount(),1);self.assertEqual(self.w.current.game_id,'SLES_512.22')
        self.w.search.setText('526.78');app.processEvents();self.assertEqual(self.w.current.game_id,'SLES_526.78')
    def test_filter_format_and_empty_selection(self):
        self.load();self.w.format.setCurrentText('ZSO');app.processEvents();self.assertEqual(self.w.table.rowCount(),0);self.assertIsNone(self.w.current);self.assertFalse(self.w.detail_buttons[0].isEnabled())
    def test_sidebar_click_filters(self):
        self.load();QTest.mouseClick(self.w.nav[1][0],Qt.MouseButton.LeftButton);self.assertEqual(self.w.filter_mode,'art');self.assertEqual(self.w.table.rowCount(),2)
        QTest.mouseClick(self.w.nav[2][0],Qt.MouseButton.LeftButton);self.assertEqual(self.w.table.rowCount(),0)
    def test_editor_button_saves_unknown_fields(self):
        self.load();g=self.w.current
        def edit_and_save(editor):editor.tabs.setCurrentIndex(editor.tabs.count()-1);editor.editor.setPlainText('Title=Custom\nUnknownKey=Preserved\n');editor.save();return QDialog.DialogCode.Accepted
        with patch.object(ui.CfgEditor,'exec',edit_and_save):QTest.mouseClick(self.w.detail_buttons[0],Qt.MouseButton.LeftButton)
        self.assertEqual(g.cfg_path.read_bytes(),b'Title=Custom\r\nUnknownKey=Preserved\r\n')
    def test_cht_editor_actual_save(self):
        self.load();g=self.w.current
        def save(editor):editor.editor.setPlainText('"Example"\n20123456 00000000\n');editor.save();return QDialog.DialogCode.Accepted
        with patch.object(ui.TextEditor,'exec',save):QTest.mouseClick(self.w.detail_buttons[4],Qt.MouseButton.LeftButton)
        self.assertIn(b'20123456 00000000',g.cheat_path.read_bytes())
    def test_worker_controls_and_complete(self):
        self.load();result=[]
        def work(progress,cancel):progress(1,1,'Hecho');return 42
        self.w.run_job('Trabajo',work,result.append);self.assertFalse(self.w.choose_btn.isEnabled());self.wait();self.assertEqual(result,[42]);self.assertTrue(self.w.choose_btn.isEnabled())
    def test_1080x720_layout_accessible(self):
        self.load();self.w.resize(1080,720);app.processEvents();self.assertGreater(self.w.table.width(),400)
        self.assertGreaterEqual(self.w.detail_buttons[-1].width(),80)
    def test_generate_index_button_ignores_ui_filters(self):
        self.load();self.w.search.setText('rayman');app.processEvents()
        self.assertEqual(self.w.table.rowCount(),1)
        with patch.object(ui.QInputDialog,'getItem',return_value=(ui.PROFILES[64],True)), patch.object(ui.QMessageBox,'information'):
            QTest.mouseClick(self.w.index_btn,Qt.MouseButton.LeftButton)
            self.assertFalse(self.w.index_btn.isEnabled());self.wait()
        self.assertEqual((self.root/'DVD/games.bin').stat().st_size,184)
        self.assertIn('2 juegos',self.w.status.text())
    def test_cancel_index_dialog_does_not_write(self):
        self.load()
        with patch.object(ui.QInputDialog,'getItem',return_value=('',False)):
            QTest.mouseClick(self.w.index_btn,Qt.MouseButton.LeftButton)
        self.assertEqual((self.root/'DVD/games.bin').stat().st_size,184)
    def test_text_editor_external_conflict(self):
        path=self.root/'CFG/test.cfg';path.parent.mkdir(exist_ok=True);path.write_bytes(b'original');editor=ui.TextEditor(path,self.w);path.write_bytes(b'external');editor.editor.setPlainText('mine')
        with patch.object(ui.QMessageBox,'warning') as warning:editor.save();warning.assert_called_once()
        self.assertEqual(path.read_bytes(),b'external');editor.original='mine';editor.close()

if __name__=='__main__':unittest.main()
