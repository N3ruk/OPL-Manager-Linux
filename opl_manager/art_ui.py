"""Art browser with remote variants, local preview and explicit publication."""
from pathlib import Path
from PyQt6.QtCore import Qt,QThread,QTimer
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import (QDialog,QVBoxLayout,QHBoxLayout,QLabel,QComboBox,QPushButton,
    QMessageBox,QFileDialog,QCheckBox,QGridLayout)
from .art import ArtClient,ART_LABELS,fetch_image,save_art_bytes
from .core import import_art,Cancelled

class ArtDialog(QDialog):
    def __init__(self,game,parent=None):
        super().__init__(parent);self.game=game;self.client=ArtClient();self.catalog={};self.worker=None;self.thread=None
        self.cache={};self.pending_close=False;self.resize(880,720);self.setWindowTitle('Arte OPL — '+game.title)
        box=QVBoxLayout(self);box.addWidget(QLabel(game.game_id+' · '+game.title))
        bar=QHBoxLayout();self.kind=QComboBox()
        for key,text in ART_LABELS.items():self.kind.addItem(text+' ('+key+')',key)
        self.kind.currentIndexChanged.connect(self.kind_changed);bar.addWidget(self.kind)
        self.variant=QComboBox();self.variant.currentIndexChanged.connect(self.preview_remote);bar.addWidget(self.variant,1)
        self.search_btn=QPushButton('Buscar en OPL Manager');self.search_btn.clicked.connect(self.search);bar.addWidget(self.search_btn);box.addLayout(bar)
        self.preview=QLabel('Buscando imágenes…');self.preview.setAlignment(Qt.AlignmentFlag.AlignCenter);self.preview.setMinimumSize(500,380);self.preview.setObjectName('cover');box.addWidget(self.preview,1)
        self.info=QLabel('');self.info.setWordWrap(True);box.addWidget(self.info)
        self.replace=QCheckBox('Sustituir arte existente (se conserva el anterior)');box.addWidget(self.replace)
        bar=QHBoxLayout();self.local_btn=QPushButton('Ver arte local');self.local_btn.clicked.connect(self.local_preview);bar.addWidget(self.local_btn)
        self.import_btn=QPushButton('Importar imagen…');self.import_btn.clicked.connect(self.import_local);bar.addWidget(self.import_btn)
        self.save_btn=QPushButton('Descargar tipo seleccionado');self.save_btn.setObjectName('primary');self.save_btn.clicked.connect(self.save_remote);bar.addWidget(self.save_btn)
        self.close_btn=QPushButton('Cerrar');self.close_btn.clicked.connect(self.reject);bar.addWidget(self.close_btn);box.addLayout(bar)
        QTimer.singleShot(0,self.search)
    def busy(self,on):
        for w in (self.kind,self.variant,self.search_btn,self.local_btn,self.import_btn,self.save_btn,self.replace):w.setEnabled(not on)
    def job(self,text,fn,done):
        if self.worker:return
        from .ui import Worker
        self.info.setText(text);self.busy(True);self.thread=QThread(self);self.worker=Worker(fn);self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.run);self.worker.done.connect(done);self.worker.failed.connect(self.failed)
        self.worker.finished.connect(self.thread.quit);self.worker.finished.connect(self.worker.deleteLater)
        self.thread.finished.connect(self.finished);self.thread.finished.connect(self.thread.deleteLater);self.thread.start()
    def failed(self,text):
        self.info.setText(text)
        if not self.pending_close and not text.startswith('Operación cancelada'):QMessageBox.warning(self,'Arte no disponible',text)
    def finished(self):
        self.worker=None;self.thread=None;self.busy(False)
        if self.pending_close:super().reject()
        elif getattr(self,'preview_pending',False):self.preview_pending=False;self.preview_remote()
    def search(self):
        def done(catalog):
            self.catalog=catalog;self.info.setText('Catálogo OPL Manager: elige un tipo y una alternativa.');self.kind_changed()
        self.job('Consultando arte en OPL Manager…',lambda p,c:self.client.catalog(self.game,c),done)
    def kind_changed(self):
        self.variant.blockSignals(True);self.variant.clear()
        for i,url in enumerate(self.catalog.get(self.kind.currentData(),[])):self.variant.addItem(f'Alternativa {i+1}',url)
        self.variant.blockSignals(False)
        if self.worker:self.preview_pending=True
        else:self.preview_remote()
    def show_bytes(self,data,text):
        pix=QPixmap();pix.loadFromData(data)
        if pix.isNull():raise ValueError('La imagen no se puede mostrar.')
        self.preview.setPixmap(pix.scaled(760,440,Qt.AspectRatioMode.KeepAspectRatio,Qt.TransformationMode.SmoothTransformation));self.info.setText(text)
    def preview_remote(self):
        if self.worker:return
        url=self.variant.currentData()
        if not url:
            self.local_preview();self.info.setText('No hay imágenes remotas de este tipo. Puedes importar una imagen local.');return
        if url in self.cache:self.show_bytes(self.cache[url],'Vista previa remota; todavía no se ha guardado en ART.');return
        def done(data):self.cache[url]=data;self.show_bytes(data,'Vista previa remota; todavía no se ha guardado en ART.')
        self.job('Descargando vista previa…',lambda p,c:fetch_image(url,c),done)
    def local_preview(self):
        path=self.game.art_path(self.kind.currentData());self.preview.clear()
        if path:self.show_bytes(path.read_bytes(),'Arte local: '+path.name)
        else:self.preview.setText('SIN ARTE LOCAL');self.info.setText('No existe este tipo de arte en la biblioteca.')
    def save_remote(self):
        if self.worker:return
        kind=self.kind.currentData();url=self.variant.currentData()
        if not url:return
        if self.game.art_path(kind) and not self.replace.isChecked():
            QMessageBox.information(self,'Arte existente','Marca «Sustituir arte existente» para reemplazar este tipo.');return
        overwrite=self.replace.isChecked()
        def job(p,c):
            data=self.cache.get(url) or fetch_image(url,c)
            from .core import cancelled
            cancelled(c);return save_art_bytes(self.game,data,kind,overwrite)
        self.job('Guardando '+kind+' en ART…',job,lambda path:self.info.setText('Guardado: '+str(path)))
    def import_local(self):
        if self.worker:return
        path,_=QFileDialog.getOpenFileName(self,'Importar arte OPL',str(Path.home()),'Imágenes (*.png *.jpg *.jpeg *.webp *.bmp)')
        if not path:return
        try:
            result=import_art(self.game,Path(path),self.kind.currentData(),self.replace.isChecked());self.local_preview();self.info.setText('Guardado: '+str(result))
        except Exception as e:QMessageBox.warning(self,'No se ha importado',str(e))
    def reject(self):
        if self.worker:
            self.pending_close=True;self.worker.cancel.set();self.info.setText('Cancelando…');return
        super().reject()
    def closeEvent(self,event):
        if self.worker:self.reject();event.ignore()
        else:event.accept()

class BatchArtOptions(QDialog):
    def __init__(self,count,parent=None):
        super().__init__(parent);self.setWindowTitle('Descargar arte por lotes');self.resize(530,380)
        box=QVBoxLayout(self);box.addWidget(QLabel(f'Juegos de la vista actual: {count}\nFuente: base original de OPL Manager.'))
        grid=QGridLayout();self.checks={}
        for i,(key,text) in enumerate(ART_LABELS.items()):
            c=QCheckBox(text+' ('+key+')');c.setChecked(key=='COV');grid.addWidget(c,i//2,i%2);self.checks[key]=c
        box.addLayout(grid);self.overwrite=QCheckBox('Sustituir imágenes existentes (conservar copia)');box.addWidget(self.overwrite)
        note=QLabel('Sin sustitución se omiten los tipos que ya existen. Si no hay una imagen en la base, se informa sin inventarla. SCR2 elige otra captura cuando está disponible.');note.setWordWrap(True);box.addWidget(note)
        bar=QHBoxLayout();b=QPushButton('Cancelar');b.clicked.connect(self.reject);bar.addWidget(b);b=QPushButton('Descargar');b.clicked.connect(self.accept);bar.addWidget(b);box.addLayout(bar)
    def kinds(self):return [k for k,c in self.checks.items() if c.isChecked()]
