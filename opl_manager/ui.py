from __future__ import annotations
import json
import math
from pathlib import Path
import random
import sys
import threading
import time
from PyQt6.QtCore import Qt,QObject,QThread,pyqtSignal,QTimer,QUrl,QSize
from PyQt6.QtGui import QColor,QFont,QPainter,QLinearGradient,QRadialGradient,QPen,QPixmap,QIcon,QDesktopServices,QAction,QActionGroup,QPalette
from PyQt6.QtWidgets import (QApplication,QMainWindow,QWidget,QFrame,QLabel,QPushButton,QLineEdit,QComboBox,
    QVBoxLayout,QHBoxLayout,QGridLayout,QFileDialog,QMessageBox,QTableWidget,QTableWidgetItem,QHeaderView,
    QAbstractItemView,QSplitter,QProgressBar,QDialog,QDialogButtonBox,QPlainTextEdit,QInputDialog,QCheckBox,
    QScrollArea,QSizePolicy,QMenu)
from . import __version__
from .themes import DEFAULT_THEME,THEMES,PALETTES,theme_key,stylesheet
from .window_theme import apply_native_palette
from .cfg_ui import CfgEditor
from .art_ui import ArtDialog,BatchArtOptions
from .art import download_art_batch
from .cfg import update_cfg_titles
from .operations import game_hashes
from .library import library_root, missing_folders, create_folders, refresh_library
from .games_index import PROFILES, generate_indexes
from .core import (BASE,Game,Cancelled,scan_library,rename_game,hash_game,export_csv,download_cover,
                   import_art,backup_text,convert_image,ART_TYPES,directory)

CONFIG=Path.home()/'.config/opl-manager-linux/settings.json'

def read_settings():
    try:
        value=json.loads(CONFIG.read_text())
        return value if isinstance(value,dict) else {}
    except (OSError,ValueError):return {}


def save_settings(**changes):
    from .core import atomic_bytes
    settings=read_settings();settings.update(changes)
    CONFIG.parent.mkdir(parents=True,exist_ok=True)
    atomic_bytes(CONFIG,json.dumps(settings,ensure_ascii=False).encode())



def label(text='',name=None):
    w=QLabel(text)
    if name:w.setObjectName(name)
    return w


def button(text,callback,primary=False):
    b=QPushButton(text);b.clicked.connect(callback)
    if primary:b.setObjectName('primary')
    b.setCursor(Qt.CursorShape.PointingHandCursor)
    return b


def size_text(n):
    for unit in ('B','KiB','MiB','GiB','TiB'):
        if n<1024 or unit=='TiB':return f'{n:.1f} {unit}'
        n/=1024


class Background(QWidget):
    def paintEvent(self,event):
        colors=self.window().colors
        p=QPainter(self);p.setRenderHint(QPainter.RenderHint.Antialiasing)
        if self.window().theme=='classic':
            p.fillRect(self.rect(),QColor(colors['background']));p.end();return
        def tinted(key,alpha):
            color=QColor(colors[key]);color.setAlpha(alpha);return color
        g=QLinearGradient(0,0,self.width(),self.height());g.setColorAt(0,QColor(colors['gradient']));g.setColorAt(.45,QColor(colors['background']));g.setColorAt(1,QColor(colors['gradient_end']));p.fillRect(self.rect(),g)
        glow=QRadialGradient(self.width()*.77,70,self.width()*.65);glow.setColorAt(0,tinted('glow',65));glow.setColorAt(1,tinted('background',0));p.fillRect(self.rect(),glow)
        rng=random.Random(22)
        for _ in range(27):
            x=rng.randint(210,max(211,self.width()));w=rng.randint(10,34);h=rng.randint(50,195);y=220-h
            tower=QLinearGradient(x,y,x+w,y+h);tower.setColorAt(0,tinted('tower',26));tower.setColorAt(1,tinted('background',0));p.fillRect(x,y,w,h,tower)
            p.setPen(QPen(tinted('sparkle',25),1));p.drawLine(x,y,x+w,y);p.drawLine(x+w,y,x+w,y+h)
        for _ in range(45):
            x=rng.randint(210,max(211,self.width()));y=rng.randint(0,min(260,self.height()))
            p.setPen(tinted('sparkle',rng.randint(20,75)));p.drawPoint(x,y)
        p.end()


class Worker(QObject):
    progress=pyqtSignal(int,int,str)
    done=pyqtSignal(object)
    failed=pyqtSignal(str)
    finished=pyqtSignal()
    def __init__(self,fn):
        super().__init__();self.fn=fn;self.cancel=threading.Event();self.last=0
    def report(self,done,total,text):
        now=time.monotonic()
        if now-self.last>.08 or done==total:
            self.last=now
            # progress may exceed signed int32 for disc sizes; scale before emitting.
            self.progress.emit(round(done/max(total,1)*1000),1000,text)
    def run(self):
        try:self.done.emit(self.fn(self.report,self.cancel))
        except Cancelled as e:self.failed.emit(str(e))
        except Exception as e:self.failed.emit(f'{type(e).__name__}: {e}')
        finally:self.finished.emit()


class TextEditor(QDialog):
    def __init__(self,path:Path,parent=None,cheats=False):
        super().__init__(parent);self.path=path;self.resize(780,590);self.setWindowTitle(('Trucos CHT' if cheats else 'Configuración CFG')+' — '+path.stem)
        self.before=path.read_bytes() if path.exists() else None
        layout=QVBoxLayout(self);layout.setContentsMargins(24,24,24,24);layout.setSpacing(14)
        layout.addWidget(label('TRUCOS OPL' if cheats else 'CONFIGURACIÓN DEL JUEGO','eyebrow'))
        layout.addWidget(label(path.name,'detailTitle'))
        info=label('Edición de texto. Se conserva una copia .bak al guardar un archivo existente.','muted');info.setWordWrap(True);layout.addWidget(info)
        self.editor=QPlainTextEdit();self.editor.setFont(QFont('DejaVu Sans Mono',11))
        if self.before is None:text='' if cheats else ''
        else:
            try:text=self.before.decode('utf-8-sig')
            except UnicodeDecodeError:text=self.before.decode('cp1252')
        self.editor.setPlainText(text);self.original=text;layout.addWidget(self.editor,1)
        self.message=label(str(path),'muted');self.message.setWordWrap(True);layout.addWidget(self.message)
        bar=QHBoxLayout();bar.addStretch();bar.addWidget(button('Cancelar',self.reject));bar.addWidget(button('Guardar',self.save,True));layout.addLayout(bar)
    def save(self):
        try:
            text=self.editor.toPlainText()
            if '\x00' in text:raise ValueError('El archivo no puede contener caracteres NUL.')
            backup_text(self.path,text,self.before);self.accept()
        except Exception as e:QMessageBox.warning(self,'No se ha guardado',str(e))
    def reject(self):
        if self.editor.toPlainText()!=self.original and QMessageBox.question(self,'Cambios sin guardar','¿Descartar los cambios de este editor?',QMessageBox.StandardButton.Discard|QMessageBox.StandardButton.Cancel,QMessageBox.StandardButton.Cancel)!=QMessageBox.StandardButton.Discard:return
        super().reject()


class MainWindow(QMainWindow):
    def __init__(self,initial=None):
        super().__init__();self.setWindowTitle('OPL Manager Linux');self.setWindowIcon(QIcon(str(BASE/'assets/opl-manager.svg')))
        self.resize(1320,940);self.setMinimumSize(1080,720)
        self.games=[];self.root=None;self.worker=None;self.thread=None;self.pending_close=False;self.filter_mode='all';self.current=None;self.scan_warnings=[];self.refresh_after_job=False
        settings=read_settings();self.theme=theme_key(settings.get('theme'));self.colors=PALETTES[self.theme]
        bg=Background();self.setCentralWidget(bg);outer=QHBoxLayout(bg);outer.setContentsMargins(0,0,0,0);outer.setSpacing(0)
        side=QFrame();side.setObjectName('sidebar');side.setFixedWidth(195);sl=QVBoxLayout(side);sl.setContentsMargins(18,32,18,22);sl.setSpacing(8)
        self.mark=label('OPL');sl.addWidget(self.mark)
        sl.addWidget(label('MANAGER','eyebrow'));sl.addSpacing(6);sl.addWidget(label('LINUX EDITION','muted'));sl.addSpacing(35)
        self.nav=[]
        for title,mode in [('▦   Biblioteca','all'),('▧   Sin carátula','art'),('△   Revisar','issues')]:
            b=button(title,lambda checked=False,m=mode:self.set_filter(m));b.setObjectName('nav');b.setCheckable(True);sl.addWidget(b);self.nav.append((b,mode))
        sl.addSpacing(26);sl.addWidget(label('HERRAMIENTAS','eyebrow'))
        self.export_btn=button('↗   Exportar lista',self.export);self.export_btn.setObjectName('nav');sl.addWidget(self.export_btn)
        self.index_btn=button('Índice avanzado…',self.generate_game_indexes);self.index_btn.setObjectName('nav');sl.addWidget(self.index_btn)
        self.index_btn.setToolTip('Los índices de 92 bytes se generan automáticamente. Este control permite elegir manualmente otro perfil.')
        sl.addStretch();sl.addWidget(label('○  △  ×  □','eyebrow'));sl.addSpacing(10)
        foot=label('Tu biblioteca.\nTu consola.','muted');sl.addWidget(foot);sl.addSpacing(16);sl.addWidget(label('v'+__version__,'muted'));outer.addWidget(side)
        main=QWidget();ml=QVBoxLayout(main);ml.setContentsMargins(26,27,26,18);ml.setSpacing(16);outer.addWidget(main,1)
        header=QHBoxLayout();titlebox=QVBoxLayout();titlebox.setSpacing(3);titlebox.addWidget(label('PLAYSTATION 2  /  OPEN PS2 LOADER','eyebrow'));titlebox.addWidget(label('Tu colección, a punto.','heading'));titlebox.addWidget(label('Juegos, carátulas y configuración en un solo lugar.','muted'));header.addLayout(titlebox,1)
        self.choose_btn=button('＋  Abrir biblioteca',self.choose_folder,True);header.addWidget(self.choose_btn,alignment=Qt.AlignmentFlag.AlignVCenter);ml.addLayout(header)
        self.path_label=label('Elige tu carpeta de juegos o la raíz de tu USB. No se moverá ningún archivo.','muted');self.path_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse);self.path_label.setWordWrap(True);ml.addWidget(self.path_label)
        stats=QHBoxLayout();stats.setSpacing(12);self.stat_values=[]
        for heading in ['JUEGOS','ESPACIO TOTAL','CON CARÁTULA','POR REVISAR']:
            card=QFrame();card.setObjectName('stat');cl=QVBoxLayout(card);cl.setContentsMargins(17,11,17,12);cl.setSpacing(3);cl.addWidget(label(heading,'eyebrow'));value=label('—','number');cl.addWidget(value);self.stat_values.append(value);stats.addWidget(card,1)
        ml.addLayout(stats)
        tools=QHBoxLayout();self.search=QLineEdit();self.search.setPlaceholderText('Buscar por título, ID o nombre de archivo…');self.search.setClearButtonEnabled(True);self.search.textChanged.connect(self.populate);tools.addWidget(self.search,1)
        self.format=QComboBox();self.format.addItems(['Todos los formatos','ISO','ZSO','VCD','UL']);self.format.currentTextChanged.connect(self.populate);tools.addWidget(self.format)
        self.refresh_btn=button('↻  Actualizar',self.refresh);tools.addWidget(self.refresh_btn)
        self.batch_btn=button('↓  Arte por lotes',self.batch_covers);tools.addWidget(self.batch_btn);ml.addLayout(tools)
        self.split=QSplitter(Qt.Orientation.Horizontal);ml.addWidget(self.split,1)
        listing=QFrame();listing.setObjectName('card');ll=QVBoxLayout(listing);ll.setContentsMargins(10,12,10,10);ll.setSpacing(7)
        top=QHBoxLayout();top.addWidget(label('BIBLIOTECA','eyebrow'));top.addStretch();self.count_label=label('0 juegos','muted');top.addWidget(self.count_label);ll.addLayout(top)
        self.table=QTableWidget(0,5);self.table.setHorizontalHeaderLabels(['JUEGO / TÍTULO','ID','TIPO','TAMAÑO','ART'])
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows);self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection);self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers);self.table.setShowGrid(False);self.table.setAlternatingRowColors(True);self.table.verticalHeader().hide();self.table.verticalHeader().setDefaultSectionSize(52);self.table.horizontalHeader().setSectionResizeMode(0,QHeaderView.ResizeMode.Stretch)
        for c,w in [(1,115),(2,58),(3,85),(4,48)]:self.table.setColumnWidth(c,w)
        self.table.setSortingEnabled(True);self.table.itemSelectionChanged.connect(self.select_game);self.table.doubleClicked.connect(lambda _:self.edit_cfg());ll.addWidget(self.table,1)
        self.empty=label('Abre una biblioteca para empezar.\n\nSe admiten ISO, ZSO, VCD y ul.cfg.','muted');self.empty.setAlignment(Qt.AlignmentFlag.AlignCenter);self.empty.setWordWrap(True);ll.addWidget(self.empty);self.split.addWidget(listing)
        details=QFrame();details.setObjectName('card');details.setMinimumWidth(290);dl=QVBoxLayout(details);dl.setContentsMargins(19,18,19,18);dl.setSpacing(10)
        dl.addWidget(label('FICHA DEL JUEGO','eyebrow'))
        self.cover=label('PS2\n\nSelecciona un juego','cover');self.cover.setFixedSize(130,186);self.cover.setAlignment(Qt.AlignmentFlag.AlignCenter);self.cover.setWordWrap(True);dl.addWidget(self.cover,alignment=Qt.AlignmentFlag.AlignHCenter)
        self.detail_title=label('Tu próxima partida','detailTitle');self.detail_title.setWordWrap(True);self.detail_title.setMaximumHeight(75);dl.addWidget(self.detail_title)
        self.detail_info=label('Selecciona un juego de la biblioteca.','muted');self.detail_info.setWordWrap(True);self.detail_info.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse);dl.addWidget(self.detail_info)
        self.issue=label('','muted');self.issue.setWordWrap(True);self.issue.setMaximumHeight(74);dl.addWidget(self.issue)
        self.detail_buttons=[]
        grid=QGridLayout();grid.setSpacing(8)
        for i,(txt,fn) in enumerate([('Editar CFG',self.edit_cfg),('Arte OPL…',self.cover_one),('Renombrar',self.rename),('Importar arte',self.import_image),('Trucos CHT',self.edit_cheats),('Convertir',self.convert),('Huellas',self.checksum),('Ver archivo',self.reveal)]):
            b=button(txt,fn);b.setStyleSheet('padding: 8px 9px;');grid.addWidget(b,i//2,i%2);self.detail_buttons.append(b)
        dl.addLayout(grid);dl.addStretch();scroll=QScrollArea();scroll.setWidgetResizable(True);scroll.setWidget(details);self.split.addWidget(scroll);self.split.setSizes([730,310]);self.split.setStretchFactor(0,1);self.split.setStretchFactor(1,0)
        status=QHBoxLayout();self.status=label('Todo listo. Los índices games.bin se actualizan automáticamente al leer la biblioteca.','muted');self.status.setWordWrap(True);status.addWidget(self.status,1);self.cancel_btn=button('Cancelar',self.cancel_work);self.cancel_btn.hide();status.addWidget(self.cancel_btn);ml.addLayout(status)
        self.progress=QProgressBar();self.progress.setTextVisible(False);self.progress.setFixedHeight(5);self.progress.hide();ml.addWidget(self.progress)
        self.make_menu();self.apply_theme(self.theme,persist=False);self.set_filter('all');self.update_actions()
        previous=settings.get('library')
        if not isinstance(previous,str):previous=None
        initial=initial or previous
        if initial and Path(initial).is_dir():QTimer.singleShot(150,lambda:self.load(Path(initial)))

    def make_menu(self):
        file=self.menuBar().addMenu('Biblioteca')
        for text,fn,shortcut in [('Abrir carpeta…',self.choose_folder,'Ctrl+O'),('Actualizar',self.refresh,'F5'),('Exportar CSV…',self.export,'Ctrl+E')]:
            a=QAction(text,self);a.triggered.connect(fn);a.setShortcut(shortcut);file.addAction(a)
        self.index_action=QAction('Generar games.bin…',self);self.index_action.triggered.connect(self.generate_game_indexes);file.addAction(self.index_action)
        tools=self.menuBar().addMenu('Herramientas')
        for title,fn in [('Descargar arte por lotes…',self.batch_covers),('Completar títulos CFG por lotes…',self.batch_cfg),('Renombrar con títulos de la base…',self.batch_rename)]:
            a=QAction(title,self);a.triggered.connect(fn);tools.addAction(a)
        self.theme_menu=self.menuBar().addMenu('Tema')
        self.theme_group=QActionGroup(self);self.theme_group.setExclusive(True);self.theme_actions={}
        for key,title in THEMES.items():
            action=QAction(title,self);action.setCheckable(True);action.setData(key)
            action.triggered.connect(lambda checked=False,k=key:self.apply_theme(k))
            self.theme_group.addAction(action);self.theme_menu.addAction(action);self.theme_actions[key]=action
        helpmenu=self.menuBar().addMenu('Ayuda');a=QAction('Qué incluye esta versión',self);a.triggered.connect(self.about);helpmenu.addAction(a)
    def apply_theme(self,key,persist=True):
        self.theme=theme_key(key);self.colors=PALETTES[self.theme];colors=self.colors
        palette=QPalette()
        for role,color in [('Window','background'),('WindowText','text'),('Base','input'),
                ('AlternateBase','alternate'),('Text','text'),('Button','button'),('ButtonText','text'),
                ('Highlight','selection'),('HighlightedText','selection_text'),('ToolTipBase','tooltip'),('ToolTipText','text')]:
            palette.setColor(getattr(QPalette.ColorRole,role),QColor(colors[color]))
        for role in ('Text','ButtonText','WindowText'):
            palette.setColor(QPalette.ColorGroup.Disabled,getattr(QPalette.ColorRole,role),QColor(colors['disabled_text']))
        native_palette=QPalette(palette)
        if self.theme=='classic':
            # Keep the classic light content, but retain dark native chrome.
            for role,color in [('Window','background'),('WindowText','text')]:
                native_palette.setColor(getattr(QPalette.ColorRole,role),QColor(PALETTES[DEFAULT_THEME][color]))
            native_palette.setColor(QPalette.ColorGroup.Disabled,QPalette.ColorRole.WindowText,QColor(PALETTES[DEFAULT_THEME]['disabled_text']))
        apply_native_palette(QApplication.instance(),native_palette)
        self.setPalette(palette);self.setStyleSheet(stylesheet(self.theme))
        self.mark.setStyleSheet(f"font-size: 49px; font-weight: 300; color: {colors['mark']}; letter-spacing: 3px;")
        self.issue.setStyleSheet(f"color: {colors['warning']}; font-size: 11px;")
        self.theme_actions[self.theme].setChecked(True)
        self.centralWidget().update();self.populate()
        if persist:
            try:save_settings(theme=self.theme)
            except OSError as e:self.error('No se ha podido recordar el tema',e)

    def about(self):
        QMessageBox.information(self,'OPL Manager Linux',
        'Versión nativa no oficial inspirada en OPL Manager 24 de danielb.\n\n'
        'Incluye: biblioteca ISO/ZSO/VCD/UL, carpetas OPL e índices CD/DVD automáticos de 92 bytes, editor CFG con controles, VMC de 8/16/32/64 MiB, ocho tipos de arte desde la API original, alternativas de fondos/capturas, lotes de arte/CFG/renombrado, CRC32/MD5/SHA-1/SHA-256, CSV, CHT y conversión ISO ↔ ZSO.\n\n'
        'No incluye aún: gestión del HDD APA/HDL, escritura USBExtreme, extracción de discos ópticos, instalación de ELF, subida de arte ni sincronización con una PS2. UL es catálogo.\n\n'
        'Los índices se actualizan al abrir la biblioteca, al arrancar y con Actualizar. Los juegos originales nunca se sobrescriben en conversiones.\n\n'
        'Títulos: base GameIndex de PCSX2. Arte: OPL Manager API V6. Fuente de portada alternativa: xlenore/ps2-covers.\nSin afiliación con Sony ni con el autor de OPL Manager.')
    def error(self,title,e):QMessageBox.warning(self,title,str(e))
    def run_job(self,text,fn,done):
        if self.worker:return
        self.status.setText(text);self.progress.setRange(0,0);self.progress.show();self.cancel_btn.show()
        self.thread=QThread(self);self.worker=Worker(fn);self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.run);self.worker.progress.connect(self.on_progress)
        self.worker.done.connect(done);self.worker.failed.connect(self.job_error);self.worker.finished.connect(self.thread.quit);self.worker.finished.connect(self.worker.deleteLater);self.thread.finished.connect(self.job_finished);self.thread.finished.connect(self.thread.deleteLater)
        self.update_actions();self.thread.start()
    def on_progress(self,value,total,text):self.progress.setRange(0,total);self.progress.setValue(value);self.status.setText(text)
    def job_error(self,text):
        self.status.setText(text)
        if not self.pending_close and not text.startswith('Operación cancelada'):self.error('La operación no se ha completado',text)
    def job_finished(self):
        self.worker=None;self.thread=None;self.progress.hide();self.cancel_btn.hide();self.update_stats();self.populate();self.update_actions()
        if self.pending_close:self.close()
        elif self.refresh_after_job:self.refresh_after_job=False;self.refresh()
    def cancel_work(self):
        if self.worker:self.worker.cancel.set();self.status.setText('Cancelando de forma segura…');self.cancel_btn.setEnabled(False)
    def choose_folder(self):
        if self.worker:return
        p=QFileDialog.getExistingDirectory(self,'Carpeta de juegos o raíz del USB',str(self.root or Path.home()))
        if p:self.load(Path(p))
    def load(self,path):
        if self.worker:return
        try:
            path=library_root(path)
            missing=missing_folders(path)
            if missing and QMessageBox.question(self,'Preparar biblioteca OPL',
                'Faltan estas carpetas OPL en:\n'+str(path)+'\n\n'+', '.join(missing)+
                '\n\n¿Quieres crearlas? Los juegos no se moverán.',
                QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.Yes)==QMessageBox.StandardButton.Yes:
                create_folders(path)
        except Exception as e:self.error('No se ha podido preparar la biblioteca',e);return
        self.run_job('Analizando juegos y actualizando games.bin…',
            lambda progress,cancel:refresh_library(path,progress,cancel),lambda data:self.loaded(path,data))
    def loaded(self,path,data):
        self.root=path.resolve();self.games,self.scan_warnings,index_result,index_error=data;self.path_label.setText(str(self.root));self.path_label.setToolTip(str(self.root));self.current=None
        try:
            save_settings(library=str(self.root))
        except OSError:pass
        self.update_stats();self.populate()
        summary=f'{len(self.games)} juegos encontrados. '
        if index_result:summary+=f'games.bin automático: {index_result.count} juegos · 92 bytes/juego. '
        if self.scan_warnings:summary+='Avisos: '+' | '.join(self.scan_warnings[:3])
        self.status.setText(summary + ('No se ha podido actualizar games.bin.' if index_error else 'Imágenes de juegos intactas.'))
        if index_error:self.error('Biblioteca cargada; índice no actualizado',index_error)
    def refresh(self):
        if self.root and not self.worker:self.load(self.root)
    def update_stats(self):
        vals=[str(len(self.games)),size_text(sum(g.size for g in self.games)),str(sum(bool(g.art_path()) for g in self.games)),str(sum(bool(g.issues) or not g.game_id for g in self.games))]
        for w,v in zip(self.stat_values,vals):w.setText(v)
    def set_filter(self,mode):
        self.filter_mode=mode
        for b,m in self.nav:b.setChecked(m==mode)
        self.populate()
    def visible_games(self):
        q=self.search.text().casefold();fmt=self.format.currentText()
        return [g for g in self.games if (not q or q in f'{g.title} {g.game_id} {g.path.name}'.casefold()) and (fmt=='Todos los formatos' or g.kind==fmt) and (self.filter_mode!='art' or not g.art_path()) and (self.filter_mode!='issues' or g.issues or not g.game_id)]
    def populate(self,*args):
        if not hasattr(self,'table'):return
        selected=self.current.path if self.current else None;selected_id=self.current.game_id if self.current else None
        games=self.visible_games();self.table.setSortingEnabled(False);self.table.setRowCount(0)
        for row,g in enumerate(games):
            self.table.insertRow(row)
            for c,text in enumerate([g.title,g.game_id or 'Sin ID',g.kind,size_text(g.size),'✓' if g.art_path() else '—']):
                item=QTableWidgetItem(text);item.setData(Qt.ItemDataRole.UserRole,g);item.setToolTip(str(g.path)+ ('\n'+'\n'.join(g.issues) if g.issues else ''))
                if c in (2,3,4):item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                if c==4:item.setForeground(QColor(self.colors['success'] if g.art_path() else self.colors['muted']))
                if c==1 and not g.game_id:item.setForeground(QColor(self.colors['warning']))
                self.table.setItem(row,c,item)
        self.table.setSortingEnabled(True);self.count_label.setText(f'{len(games)} de {len(self.games)} juegos');self.empty.setVisible(not games)
        self.empty.setText('No hay juegos que coincidan con este filtro.' if self.games else 'Abre tu carpeta de juegos o la raíz del USB.\n\nISO · ZSO · VCD · ul.cfg')
        if games:
            chosen=next((i for i in range(self.table.rowCount()) if self.table.item(i,0).data(Qt.ItemDataRole.UserRole).path==selected and self.table.item(i,0).data(Qt.ItemDataRole.UserRole).game_id==selected_id),0);self.table.selectRow(chosen)
        else:self.current=None;self.select_game()
    def select_game(self):
        row=self.table.currentRow();self.current=self.table.item(row,0).data(Qt.ItemDataRole.UserRole) if row>=0 and self.table.item(row,0) else None
        self.cover.clear()
        if self.current:
            g=self.current;self.detail_title.setText(g.title);self.detail_title.setToolTip(g.title);self.detail_info.setText(f'{g.game_id or "Sin ID reconocido"}   ·   {g.kind} / {g.media}\n{g.region or "Región desconocida"}   ·   {size_text(g.size)}\nID: {g.id_source}');self.issue.setText('\n'.join(g.issues));self.issue.setToolTip('\n'.join(g.issues))
            art=g.art_path()
            if art:
                pix=QPixmap(str(art));self.cover.setPixmap(pix.scaled(128,184,Qt.AspectRatioMode.KeepAspectRatio,Qt.TransformationMode.SmoothTransformation))
            else:self.cover.setText('PLAYSTATION 2\n\n'+(g.game_id or 'SIN ID')+'\n\nSIN CARÁTULA')
        else:self.detail_title.setText('Tu próxima partida');self.detail_info.setText('Selecciona un juego de la biblioteca.');self.issue.clear();self.cover.setText('PS2\n\nTu colección empieza aquí')
        self.update_actions()
    def update_actions(self):
        if not hasattr(self,'detail_buttons'):return
        busy=self.worker is not None;g=self.current
        for b in (self.choose_btn,self.refresh_btn,self.export_btn,self.batch_btn):b.setEnabled(not busy)
        self.index_btn.setEnabled(not busy and self.root is not None)
        if hasattr(self,'index_action'):self.index_action.setEnabled(not busy and self.root is not None)
        self.cancel_btn.setEnabled(True)
        for i,b in enumerate(self.detail_buttons):
            enabled=g is not None and not busy
            if g:
                if i in (0,1,3,4):enabled=enabled and bool(g.game_id)
                if i==2:enabled=enabled and g.kind!='UL'
                if i==5:enabled=enabled and g.kind in ('ISO','ZSO')
            b.setEnabled(enabled)
    def edit_cfg(self):
        g=self.current
        if not g or not g.game_id or self.worker:return
        games=[game for game in self.games if game.game_id]
        try:
            while True:
                editor=CfgEditor(g,self);result=editor.exec()
                if not editor.navigation:
                    if result:self.status.setText(f'CFG guardado: {g.cfg_path.name}')
                    break
                g=games[(games.index(g)+editor.navigation)%len(games)]
        except Exception as e:self.error('No se ha podido abrir el CFG',e)
    def edit_cheats(self):
        g=self.current
        if not g or not g.game_id or self.worker:return
        try:
            if TextEditor(g.cheat_path,self,True).exec():self.status.setText(f'CHT guardado: {g.cheat_path.name}')
        except Exception as e:self.error('No se han podido abrir los trucos',e)
    def rename(self):
        g=self.current
        if not g or self.worker:return
        dialog=QDialog(self);dialog.setWindowTitle('Renombrar juego');layout=QVBoxLayout(dialog);layout.setContentsMargins(24,24,24,24);layout.setSpacing(13)
        layout.addWidget(label('Nuevo título del archivo','detailTitle'));edit=QLineEdit(g.path.stem)
        import re
        edit.setText(re.sub(r'(?i)^[A-Z]{4}[-_ .]?\d{3}[. -]?\d{2}[. _-]*','',g.path.stem));layout.addWidget(edit)
        classic=QCheckBox('Nombre clásico OPL: ID.Título.iso (máximo 32 bytes de título)');classic.setChecked(bool(g.game_id));classic.setEnabled(bool(g.game_id));layout.addWidget(classic)
        preview=label('','muted');preview.setWordWrap(True);layout.addWidget(preview)
        def update():preview.setText('Resultado: '+(g.game_id+'.' if classic.isChecked() else '')+edit.text().strip()+g.path.suffix.lower())
        edit.textChanged.connect(update);classic.toggled.connect(update);update()
        box=QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel|QDialogButtonBox.StandardButton.Ok);box.accepted.connect(dialog.accept);box.rejected.connect(dialog.reject);layout.addWidget(box)
        if dialog.exec():
            try:
                target=rename_game(g,edit.text(),classic.isChecked());g.path=target;self.populate();self.status.setText('Archivo renombrado: '+target.name);self.refresh()
            except Exception as e:self.error('No se ha renombrado',e)
    def cover_one(self):
        g=self.current
        if not g or not g.game_id or self.worker:return
        try:ArtDialog(g,self).exec();self.art_updated('Gestión de arte terminada.')
        except Exception as e:self.error('No se ha podido abrir el arte',e)
    def art_updated(self,text):self.update_stats();self.populate();self.status.setText(text)
    def batch_covers(self):
        if self.worker:return
        games=[g for g in self.visible_games() if g.game_id]
        if not games:QMessageBox.information(self,'Arte','No hay juegos con ID en la vista actual.');return
        dialog=BatchArtOptions(len(games),self)
        if not dialog.exec() or not dialog.kinds():return
        kinds=dialog.kinds();overwrite=dialog.overwrite.isChecked()
        def done(result):
            saved,missing,errors=result
            self.art_updated(f'Arte: {saved} imágenes guardadas · {missing} no disponibles · {len(errors)} errores.')
            QMessageBox.information(self,'Descarga de arte',f'Guardadas: {saved}\nNo disponibles en la base: {missing}\nErrores: {len(errors)}'+('\n\n'+'\n'.join(errors[:12]) if errors else ''))
        self.run_job('Descargando arte OPL…',lambda p,c:download_art_batch(games,kinds,overwrite,p,c),done)
    def import_image(self):
        g=self.current
        if not g or not g.game_id or self.worker:return
        kind,ok=QInputDialog.getItem(self,'Tipo de arte','Imagen OPL:',list(ART_TYPES),0,False)
        if not ok:return
        path,_=QFileDialog.getOpenFileName(self,'Imagen para '+g.game_id,str(Path.home()),'Imágenes (*.png *.jpg *.jpeg *.webp *.bmp)')
        if not path:return
        existing=g.art_path(kind)
        if existing and QMessageBox.question(self,'Sustituir imagen',f'Ya existe {existing.name}. ¿Sustituir este tipo de arte?')!=QMessageBox.StandardButton.Yes:return
        try:dest=import_art(g,Path(path),kind,bool(existing));self.art_updated('Imagen guardada: '+dest.name)
        except Exception as e:self.error('No se ha importado la imagen',e)
    def batch_cfg(self):
        if self.worker:return
        games=[g for g in self.visible_games() if g.game_id]
        if not games:return
        if QMessageBox.question(self,'Completar CFG por lotes',f'Se añadirá el título local a los CFG que no tengan Title ({len(games)} juegos visibles).\nLos títulos existentes y las demás opciones no se cambiarán. ¿Continuar?')!=QMessageBox.StandardButton.Yes:return
        def done(result):
            saved,errors=result;self.status.setText(f'CFG: {saved} títulos completados · {len(errors)} errores.')
            if errors:self.error('CFG no completados','\n'.join(errors[:12]))
        self.run_job('Completando CFG…',lambda p,c:update_cfg_titles(games,p,c),done)
    def batch_rename(self):
        if self.worker:return
        games=[g for g in self.visible_games() if g.game_id and g.kind in ('ISO','ZSO')]
        if not games:return
        if QMessageBox.question(self,'Renombrar por lotes',f'Se usarán los títulos de la base local en {len(games)} ISO/ZSO visibles.\nFormato moderno: Título.iso/zso. No se sobrescriben archivos.\n¿Continuar?')!=QMessageBox.StandardButton.Yes:return
        def job(progress,cancel):
            errors=[];saved=0
            for i,g in enumerate(games):
                if cancel.is_set():errors.append('Operación cancelada; los juegos ya renombrados se conservan.');break
                try:g.path=rename_game(g,g.title,False);saved+=1
                except Exception as e:errors.append(f'{g.path.name}: {e}')
                progress(i+1,len(games),g.title)
            # Publish current filenames even when a batch was stopped midway.
            result=refresh_library(self.root,progress,None)
            return saved,errors,result
        def done(result):
            saved,errors,data=result;self.loaded(self.root,data);self.status.setText(f'{saved} juegos procesados · {len(errors)} avisos. '+('Índice no actualizado.' if data[3] else 'Índices actualizados.'))
            if errors:self.error('Renombrados no completados','\n'.join(errors[:12]))
        self.run_job('Renombrando juegos…',job,done)
    def checksum(self):
        g=self.current
        if not g or self.worker:return
        def done(values):
            self.status.setText('CRC32, MD5, SHA-1 y SHA-256 calculados.')
            d=QDialog(self);d.setWindowTitle('Huellas — '+g.title);d.resize(730,340);v=QVBoxLayout(d);v.addWidget(label(g.path.name));edit=QPlainTextEdit('\n\n'.join(k+': '+value for k,value in values.items()));edit.setReadOnly(True);v.addWidget(edit);v.addWidget(label('Huellas del archivo (partes UL concatenadas). No se comparan automáticamente con Redump.','muted'));v.addWidget(button('Cerrar',d.accept));d.exec()
        self.run_job('Calculando CRC32, MD5, SHA-1 y SHA-256…',lambda p,c:game_hashes(g,p,c),done)
    def convert(self):
        g=self.current
        if not g or self.worker:return
        ext='.zso' if g.kind=='ISO' else '.iso';path,_=QFileDialog.getSaveFileName(self,'Guardar conversión (se conserva el original)',str(g.path.with_suffix(ext)),f'Imagen (*{ext})')
        if not path:return
        dest=Path(path)
        if dest.suffix.lower()!=ext:dest=dest.with_suffix(ext)
        if dest.exists():self.error('No se ha iniciado','El destino ya existe. Elige otro nombre; no se sobrescriben juegos.');return
        def done(path):
            self.refresh_after_job=True;self.status.setText('Conversión terminada: '+str(path))
        self.run_job('Convirtiendo; el original se conserva…',lambda p,c:convert_image(g.path,dest,p,c),done)
    def reveal(self):
        if self.current:QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.current.path.parent)))
    def export(self):
        if self.worker:return
        path,_=QFileDialog.getSaveFileName(self,'Exportar juegos visibles',str(Path.home()/'biblioteca-opl.csv'),'CSV (*.csv)')
        if path:
            try:export_csv(self.visible_games(),path);self.status.setText('Lista CSV exportada: '+path)
            except Exception as e:self.error('No se ha podido exportar',e)
    def generate_game_indexes(self):
        if self.worker or not self.root:return
        profile,ok=QInputDialog.getItem(self,'Generar games.bin',
            'Se actualizará games.bin en DVD y CD (o solo la carpeta elegida).\n'
            'Incluye todos los ISO/ZSO, aunque haya filtros activos. No modifica juegos ni el servidor.\n\n'
            'Formato del índice:',list(PROFILES.values()),0,False)
        if not ok:return
        name_bytes=next(size for size,text in PROFILES.items() if text==profile)
        def done(result):
            detail='\n'.join(f'{path}: {count} juegos' for path,count in result.files.items())
            self.status.setText(f'games.bin actualizado: {result.count} juegos en {len(result.files)} carpetas. ISO/ZSO intactos.')
            QMessageBox.information(self,'Índices generados',detail+'\n\nVuelve a cargar o actualizar la lista en OPL.\nSi se sirve un disco virtual ya abierto, la nueva lista puede requerir su próxima apertura; no se ha tocado el servidor.')
        self.run_job('Generando índices games.bin…',lambda p,c:generate_indexes(self.root,name_bytes,p,c),done)
    def closeEvent(self,event):
        if self.worker:
            if not self.pending_close and QMessageBox.question(self,'Operación en curso','¿Cancelar la operación y cerrar al terminar?',QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.No,QMessageBox.StandardButton.No)!=QMessageBox.StandardButton.Yes:event.ignore();return
            self.pending_close=True;self.cancel_work();event.ignore();return
        event.accept()


def main():
    app=QApplication(sys.argv);app.setApplicationName('OPL Manager Linux');app.setDesktopFileName('opl-manager-linux');app.setOrganizationName('N3ruk');app.setStyle('Fusion');app.setWindowIcon(QIcon(str(BASE/'assets/opl-manager.svg')))
    root=None
    if '--library' in sys.argv:
        i=sys.argv.index('--library')
        if len(sys.argv)>i+1:root=sys.argv[i+1]
    window=MainWindow(root);window.show()
    return app.exec()
