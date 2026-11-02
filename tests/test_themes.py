import json
import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from pathlib import Path
import tempfile,time,unittest
from unittest.mock import patch
from PyQt6.QtWidgets import QApplication,QLabel
from PyQt6.QtGui import QPalette
from PyQt6.QtTest import QTest
from opl_manager import ui
from opl_manager.themes import THEMES,PALETTES
from test_core import make_iso

app=QApplication.instance() or QApplication([])

class ThemeTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        self.config=patch.object(ui,'CONFIG',self.root/'preferences.json');self.config.start()
        self.windows=[]
    def tearDown(self):
        for w in self.windows:
            deadline=time.monotonic()+8
            while w.worker and time.monotonic()<deadline:app.processEvents();QTest.qWait(10)
            w.close()
        app.processEvents();self.config.stop();self.tmp.cleanup()
    def window(self):
        w=ui.MainWindow();self.windows.append(w);w.show();app.processEvents();return w
    def test_default_menu_and_requested_text(self):
        w=self.window();self.assertEqual(w.theme,'ugm')
        self.assertEqual([a.text() for a in w.menuBar().actions()],['Biblioteca','Herramientas','Tema','Ayuda'])
        self.assertEqual([a.text() for a in w.theme_menu.actions()],list(THEMES.values()))
        self.assertEqual(ui.PROFILES[64],'OPL legacy · 92bytes/juego')
        self.assertFalse(any('sin windows' in l.text().lower() for l in w.findChildren(QLabel)))
    def test_menu_switches_live_exclusively_and_updates_open_dialog(self):
        make_iso(self.root/'DVD/test.iso');ui.create_folders(self.root)
        from opl_manager.core import inspect_game
        w=self.window();d=ui.CfgEditor(inspect_game(self.root/'DVD/test.iso',self.root,{}),w);d.show()
        styles=set()
        for key in THEMES:
            w.theme_actions[key].trigger();app.processEvents();styles.add(w.styleSheet())
            self.assertEqual(w.theme,key)
            self.assertEqual([k for k,a in w.theme_actions.items() if a.isChecked()],[key])
            self.assertEqual(d.palette().color(QPalette.ColorRole.Window).name(),PALETTES[key]['background'])
            self.assertEqual(json.loads(ui.CONFIG.read_text())['theme'],key)
        self.assertEqual(len(styles),5);d.close()
    def test_theme_library_and_unknown_settings_survive_reload(self):
        make_iso(self.root/'DVD/test.iso');ui.create_folders(self.root)
        ui.CONFIG.write_text(json.dumps({'library':str(self.root),'future-option':42}))
        w=self.window();w.theme_actions['green'].trigger()
        deadline=time.monotonic()+8
        while (w.root is None or w.worker) and time.monotonic()<deadline:app.processEvents();QTest.qWait(10)
        self.assertEqual(len(w.games),1)
        saved=json.loads(ui.CONFIG.read_text())
        self.assertEqual(saved,{'library':str(self.root),'future-option':42,'theme':'green'})
        other=self.window();self.assertEqual(other.theme,'green')
        QTest.qWait(220);app.processEvents()
    def test_invalid_preferences_fall_back_to_ugm(self):
        for value in ('broken','[]','{"theme": "missing"}','{"theme": []}'):
            ui.CONFIG.write_text(value);w=self.window();self.assertEqual(w.theme,'ugm');w.close()
    def test_switch_keeps_filter_and_selection_and_minimum_layout(self):
        from opl_manager.library import refresh_library
        make_iso(self.root/'DVD/test.iso');ui.create_folders(self.root)
        w=self.window();w.loaded(self.root,refresh_library(self.root));w.search.setText('526.78')
        selected=w.current.path;w.resize(1080,720)
        for key in THEMES:
            w.theme_actions[key].trigger();app.processEvents()
            self.assertEqual(w.current.path,selected);self.assertEqual(w.search.text(),'526.78')
            self.assertEqual(w.table.rowCount(),1);self.assertGreater(w.table.width(),400)
            self.assertGreaterEqual(w.detail_buttons[-1].width(),80)
