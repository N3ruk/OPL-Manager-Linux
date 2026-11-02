from pathlib import Path
from PyQt6.QtWidgets import (QDialog,QVBoxLayout,QHBoxLayout,QFormLayout,QTabWidget,QWidget,QLineEdit,
    QComboBox,QCheckBox,QInputDialog,QPlainTextEdit,QPushButton,QLabel,QMessageBox,QFileDialog,QScrollArea)
from .cfg import CfgDocument,ASPECTS,VMODES,SCANS,DEVICES,GSM_MODES,MODE_HELP
from .core import backup_text,directory

class CfgEditor(QDialog):
    def __init__(self,game,parent=None):
        super().__init__(parent);self.game=game;self.path=game.cfg_path;self.resize(850,740)
        self.setWindowTitle('Editar CFG — '+game.title)
        self.before=self.path.read_bytes() if self.path.exists() else None
        try:text=self.before.decode('utf-8-sig') if self.before else ''
        except UnicodeDecodeError:text=self.before.decode('cp1252')
        self.original=text;self.doc=CfgDocument(text);self.navigation=0
        if self.before is None:self.doc.set('CfgVersion','8');self.doc.set('$ConfigSource','1')
        self.controls={};self.dirty=False;self.updating=False;self.raw_active=False
        outer=QVBoxLayout(self);outer.addWidget(QLabel(f'{game.game_id} · {self.path.name}'))
        self.tabs=QTabWidget();outer.addWidget(self.tabs,1)
        self.forms={}
        for name in ('Información','Compatibilidad','GSM','VMC y trucos','Ajustes globales'):
            page=QWidget();form=QFormLayout(page);form.setSpacing(12);scroll=QScrollArea();scroll.setWidgetResizable(True);scroll.setWidget(page);self.tabs.addTab(scroll,name);self.forms[name]=form
        f=self.forms['Información']
        self.text_field(f,'Title','Título')
        genres=['Action','Adventure','Arcade / Retro','Art / Build','Cards / Casino','Compilation','Dance / Exercise','Fighting','Flight Simulator','Horror','Hunting / Outdoors','Miscellaneous','Music','Pinball','Platform','Puzzle','Racing','RPG','Sci-Fi','Shooter','Simulation / SIM','Sports','Strategy','Survival','Third-Person Action','Third-Person Shooter','Turn-Based Strategy','Visual Novel']
        self.combo(f,'Genre','Género',[('', 'Sin especificar')]+[(g,g) for g in genres])
        self.text_field(f,'Release','Lanzamiento');self.text_field(f,'Developer','Desarrollador')
        self.combo(f,'Players','Jugadores',[('', 'Sin especificar')]+[(f'players/{i}',str(i)) for i in range(1,5)],True)
        self.combo(f,'Vmode','Sistema de vídeo',VMODES,True);self.combo(f,'Scan','Escaneo',SCANS,True)
        self.combo(f,'Aspect','Relación de aspecto',ASPECTS,True)
        self.combo(f,'Rating','Puntuación',[('', 'Sin especificar')]+[(f'rating/{i}',str(i)+' / 5') for i in range(1,6)],True)
        ratings=[('', 'Sin especificar')]
        for system,values in [('pegi',['3','7','12','16','18']),('esrb',['3','e','10','teen','17','18']),('cero',['a','b','c','d','z','demo','pending']),('bbfc',['pg','u','12','15','18']),('dejus',['l','10','12','14','16','18']),('elspa',['3','3a','11','11a','15','15a','18','18a']),('esra',['3','7','12','15','18']),('ofcl',['e','g','pg','m','ma','r','x']),('usk',['0','6','12','16','18'])]:
            ratings.extend((system+'/'+v,system.upper()+' '+v.upper()) for v in values)
        self.combo(f,'Parental','Clasificación por edades',ratings,True)
        self.text_field(f,'Description','Descripción (máx. 255 caracteres)');self.text_field(f,'Notes','Notas')
        title=QPushButton('Usar título de la base local');title.clicked.connect(lambda:self.controls['Title'].setText(game.title));f.addRow(title)
        f=self.forms['Compatibilidad'];self.modes=[]
        for i,helptext in enumerate(MODE_HELP):
            c=QCheckBox(f'Modo {i+1} — {helptext}');c.setChecked(bool(self.doc.compatibility()&(1<<i)));c.toggled.connect(self.mode_change);f.addRow(c);self.modes.append(c)
        self.combo(f,'Device','Dispositivos compatibles',DEVICES,True)
        self.combo(f,'$DMA','DMA',[('', 'Predeterminado (UDMA 4)')]+[(str(i),v) for i,v in enumerate(['MDMA 0','MDMA 1','MDMA 2','UDMA 0','UDMA 1','UDMA 2','UDMA 3'])])
        self.text_field(f,'$DNAS','DNAS (si la versión de OPL lo admite)');self.text_field(f,'$AltStartup','Ejecutable alternativo')
        f=self.forms['GSM'];self.check(f,'$EnableGSM','Activar GSM')
        self.combo(f,'$GSMVMode','Modo de vídeo',[('',GSM_MODES[0])]+[(str(i),v) for i,v in enumerate(GSM_MODES) if i])
        self.text_field(f,'$GSMXOffset','Ajuste horizontal');self.text_field(f,'$GSMYOffset','Ajuste vertical')
        self.check(f,'$GSMSkipVideos','Omitir vídeos');self.check(f,'$GSMFIELDFix','Emular FIELD flipping')
        f=self.forms['VMC y trucos']
        for slot in (0,1):
            key=f'$VMC_{slot}';self.text_field(f,key,f'VMC ranura {slot} (nombre sin .bin)')
            b=QPushButton(f'Elegir VMC {slot} existente…');b.clicked.connect(lambda checked=False,k=key:self.browse_vmc(k));f.addRow(b)
            new=QPushButton(f'Crear VMC {slot}…');new.clicked.connect(lambda checked=False,k=key:self.new_vmc(k));f.addRow(new)
        self.check(f,'$EnableCheat','Activar trucos');self.combo(f,'Cheat','Dispositivo de trucos',[('', 'Sin especificar'),('Codebreaker','Codebreaker'),('ps2rd','ps2rd')])
        f=self.forms['Ajustes globales']
        for key,title in [('$ConfigSource','Configuración'),('$GSMSource','GSM'),('$CheatsSource','Trucos'),('$PADEMUSource','PADEMU')]:
            self.combo(f,key,title,[('', 'Global / predeterminado'),('1','Por juego')])
        self.check(f,'$EnablePadEmu','Activar PADEMU');self.text_field(f,'$PadEmuSettings','Opciones PADEMU (valor OPL)')
        self.editor=QPlainTextEdit(self.doc.text());self.tabs.addTab(self.editor,'Texto CFG / vista previa')
        self.tabs.currentChanged.connect(self.tab_changed)
        self.note=QLabel('Se conservan las claves desconocidas. Guardado con copia .bak y detección de cambios externos.');self.note.setWordWrap(True);outer.addWidget(self.note)
        bar=QHBoxLayout()
        if parent is not None and hasattr(parent,'games') and len(parent.games)>1:
            for title,delta in [('← Anterior',-1),('Siguiente →',1)]:
                nav=QPushButton(title);nav.clicked.connect(lambda checked=False,d=delta:self.navigate(d));bar.addWidget(nav)
        bar.addStretch();b=QPushButton('Cancelar');b.clicked.connect(self.reject);bar.addWidget(b)
        b=QPushButton('Guardar CFG');b.setObjectName('primary');b.clicked.connect(self.save);bar.addWidget(b);outer.addLayout(bar)
    def navigate(self,delta):
        changed=self.dirty or (self.raw_active and self.editor.toPlainText()!=self.doc.text().rstrip('\n'))
        if changed:
            answer=QMessageBox.question(self,'Cambiar de juego','¿Guardar los cambios antes de cambiar de juego?',QMessageBox.StandardButton.Save|QMessageBox.StandardButton.Discard|QMessageBox.StandardButton.Cancel,QMessageBox.StandardButton.Save)
            if answer==QMessageBox.StandardButton.Cancel:return
            if answer==QMessageBox.StandardButton.Save:
                self.save()
                if self.result()!=QDialog.DialogCode.Accepted:return
        self.navigation=delta;self.done(2 if delta<0 else 3)
    def text_field(self,form,key,title):
        edit=QLineEdit(self.doc.get(key));edit.textChanged.connect(lambda value,k=key:self.set_value(k,value));form.addRow(title,edit);self.controls[key]=edit
    def combo(self,form,key,title,choices,companion=False):
        c=QComboBox()
        for value,label in choices:c.addItem(label,value)
        value=self.doc.get(key);i=c.findData(value)
        if i<0:c.addItem(value,value);i=c.count()-1
        c.setCurrentIndex(i);c.currentIndexChanged.connect(lambda _,k=key,w=c,cp=companion:self.combo_change(k,w,cp));form.addRow(title,c);self.controls[key]=c
    def check(self,form,key,title):
        c=QCheckBox(title);c.setChecked(self.doc.get(key)=='1');c.toggled.connect(lambda on,k=key:self.set_value(k,'1' if on else ''));form.addRow(c);self.controls[key]=c
    def set_value(self,key,value):
        if self.updating:return
        self.doc.set(key,value);self.dirty=True
    def combo_change(self,key,widget,companion):
        if self.updating:return
        self.set_value(key,widget.currentData())
        if companion:self.set_value(key+'Text',widget.currentText() if widget.currentData() else '')
    def mode_change(self):
        if self.updating:return
        # Preserve unknown higher mode bits from newer configurations.
        high=self.doc.compatibility()&~255
        active=[i for i,c in enumerate(self.modes) if c.isChecked()]
        self.doc.set_modes(active)
        if high:self.doc.set('$Compatibility',str(high|sum(1<<i for i in active)))
        self.dirty=True
    def browse_vmc(self,key):
        p,_=QFileDialog.getOpenFileName(self,'Elegir VMC',str(directory(self.game.root,'VMC')),'VMC (*.bin)')
        if p:
            path=Path(p)
            if path.parent.resolve()!=directory(self.game.root,'VMC').resolve():
                QMessageBox.warning(self,'VMC fuera de la biblioteca','Elige un archivo dentro de la carpeta VMC de esta biblioteca.');return
            self.controls[key].setText(path.stem)
    def new_vmc(self,key):
        from .vmc import create_vmc
        name,ok=QInputDialog.getText(self,'Nueva VMC','Nombre (sin .bin):',text=self.game.game_id+'_'+key[-1])
        if not ok:return
        name=name.strip()
        if not name or any(c in name for c in '/\\:*?"<>|') or name in ('.','..') or name.lower().endswith('.bin'):
            QMessageBox.warning(self,'Nombre no válido','Usa un nombre de archivo sin rutas ni extensión .bin.');return
        size,ok=QInputDialog.getItem(self,'Tamaño VMC','Capacidad:', ['8','16','32','64'],0,False)
        if not ok:return
        try:
            path=create_vmc(directory(self.game.root,'VMC')/(name+'.bin'),int(size))
            self.controls[key].setText(path.stem);self.note.setText('VMC creada y formateada: '+path.name+'. Guarda el CFG para asignarla.')
        except Exception as e:QMessageBox.warning(self,'No se ha creado la VMC',str(e))
    def tab_changed(self,index):
        if index==self.tabs.count()-1:
            self.editor.setPlainText(self.doc.text());self.raw_active=True
        elif self.raw_active:
            text=self.editor.toPlainText()
            if text!=self.doc.text().rstrip('\n'):
                self.doc=CfgDocument(text);self.dirty=True;self.sync_controls()
            self.raw_active=False
    def sync_controls(self):
        self.updating=True
        for key,w in self.controls.items():
            value=self.doc.get(key)
            if isinstance(w,QLineEdit):w.setText(value)
            elif isinstance(w,QCheckBox):w.setChecked(value=='1')
            else:
                idx=w.findData(value)
                if idx<0:w.addItem(value,value);idx=w.count()-1
                w.setCurrentIndex(idx)
        for i,c in enumerate(self.modes):c.setChecked(bool(self.doc.compatibility()&(1<<i)))
        self.updating=False
    def save(self):
        try:
            if self.tabs.currentIndex()==self.tabs.count()-1:self.doc=CfgDocument(self.editor.toPlainText())
            if len(self.doc.get('Description'))>255:raise ValueError('La descripción admite hasta 255 caracteres.')
            for key in ('$GSMXOffset','$GSMYOffset'):
                v=self.doc.get(key)
                if v and not -128<=int(v)<=127:raise ValueError(f'{key}: usa un entero entre -128 y 127.')
            for slot in (0,1):
                name=self.doc.get(f'$VMC_{slot}')
                if name and (any(c in name for c in '/\\:*?"<>|') or name in ('.','..') or name.lower().endswith('.bin')):
                    raise ValueError('VMC: usa solo el nombre del archivo, sin ruta ni extensión .bin.')
            backup_text(self.path,self.doc.text(),self.before);self.dirty=False;self.accept()
        except Exception as e:QMessageBox.warning(self,'No se ha guardado el CFG',str(e))
    def reject(self):
        changed=self.dirty or (self.tabs.currentIndex()==self.tabs.count()-1 and self.editor.toPlainText()!=self.original.rstrip('\n'))
        if changed and QMessageBox.question(self,'Cambios sin guardar','¿Descartar los cambios del CFG?',QMessageBox.StandardButton.Discard|QMessageBox.StandardButton.Cancel,QMessageBox.StandardButton.Cancel)!=QMessageBox.StandardButton.Discard:return
        super().reject()
