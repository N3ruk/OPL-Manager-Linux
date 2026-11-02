"""Lossless-by-default OPL CFG editing; interoperable with OPL Manager V24."""
import re
from .core import backup_text

KEY_RE = re.compile(r'^\s*([^#;=][^=]*?)\s*=(.*)$')

class CfgDocument:
    def __init__(self, text=''):
        self.lines = text.replace('\r\n', '\n').replace('\r', '\n').splitlines()
    def get(self, key, default=''):
        for line in self.lines:
            m=KEY_RE.match(line)
            if m and m[1].strip().casefold()==key.casefold():return m[2].strip()
        return default
    def set(self, key, value):
        value=str(value)
        if any(c in value for c in ('\x00','\r','\n')):
            raise ValueError(f'{key}: no se admiten saltos de línea ni NUL.')
        found=False;lines=[]
        for line in self.lines:
            m=KEY_RE.match(line)
            if m and m[1].strip().casefold()==key.casefold():
                if not found and value:lines.append(key+'='+value)
                found=True
            else:lines.append(line)
        if not found and value:lines.append(key+'='+value)
        self.lines=lines
    def text(self):return '\n'.join(self.lines)+ ('\n' if self.lines else '')
    def compatibility(self):
        try:return int(self.get('$Compatibility','0'))
        except ValueError:return 0
    def set_modes(self, enabled):
        bits=sum(1 << i for i in enabled)
        self.set('$Compatibility',str(bits) if bits else '')
        self.set('Modes','+'.join(str(i+1) for i in enabled))

# CFG control values for OPL metadata and compatibility options.
ASPECTS=[('', 'Sin especificar'),('aspect/s','4:3'),('aspect/w','16:9'),('aspect/w1','16:9 (ps2rd)'),('aspect/w2','16:9 (HexISO)')]
VMODES=[('', 'Sin especificar'),('vmode/pal','PAL'),('vmode/ntsc','NTSC'),('vmode/multi','MULTI')]
SCANS=[('', 'Sin especificar')]+[(f'scan/{v}',label) for v,label in [('240p','240p'),('240p1','240p (HexISO)'),('480i','480i'),('480p','480p'),('480p1','480p (Triángulo + Cruz)'),('480p2','480p (Círculo + Cruz)'),('480p3','480p (GSM)'),('480p4','480p (ps2rd)'),('480p5','480p (HexISO)'),('576i','576i'),('576p','576p (GSM)'),('720p','720p (GSM)'),('1080i','1080i'),('1080i2','1080i (GSM)'),('1080p','1080p (GSM)')]]
DEVICES=[('', 'Sin especificar'),('device/1','USB'),('device/2','USB + ETH'),('device/3','USB + HDD'),('device/4','ETH + HDD'),('device/5','ETH'),('device/6','HDD'),('device/all','USB + ETH + HDD')]
GSM_MODES=['NTSC','NTSC no entrelazado','PAL','PAL no entrelazado','PAL 60 Hz','PAL 60 Hz no entrelazado','PS1 NTSC 480p','PS1 PAL 576p','HDTV 480p 60 Hz','HDTV 576p 50 Hz','HDTV 720p 60 Hz','HDTV 1080i 60 Hz','HDTV 1080i no entrelazado','HDTV 1080p 60 Hz','VGA 640×480p 60 Hz','VGA 640×480p 72 Hz','VGA 640×480p 75 Hz','VGA 640×480p 85 Hz','VGA 640×480i 60 Hz']
MODE_HELP=['Núcleo EE alternativo','Método de lectura alternativo','Desenganchar syscalls','Omitir vídeos PSS','Emular DVD de doble capa','Desactivar IGR','Reducir búfer cdvdfsv','Ocultar módulo DEV9']

def update_cfg_titles(games, progress=None, cancel=None):
    from .core import cancelled
    saved=0;errors=[]
    for i,g in enumerate(games):
        cancelled(cancel)
        if g.game_id:
            try:
                path=g.cfg_path;before=path.read_bytes() if path.exists() else None
                try:text=before.decode('utf-8-sig') if before else ''
                except UnicodeDecodeError:text=before.decode('cp1252')
                doc=CfgDocument(text)
                if not doc.get('Title'):
                    if before is None:doc.set('CfgVersion','8')
                    doc.set('Title',g.title);backup_text(path,doc.text(),before);saved+=1
            except (ValueError,OSError) as e:errors.append(f'{g.path.name}: {e}')
        if progress:progress(i+1,len(games),g.title)
    return saved,errors
