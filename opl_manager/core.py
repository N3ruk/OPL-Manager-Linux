"""Native OPL library operations. No Windows executables are executed."""
from __future__ import annotations
import csv
import ctypes
import ctypes.util
import hashlib
import io
import json
import math
import os
from pathlib import Path
import re
import struct
import tempfile
import threading
import urllib.request
from dataclasses import dataclass, field
from typing import Callable

BASE = Path(__file__).resolve().parent.parent
ID_RE = re.compile(r'(?i)(?<![A-Z0-9])([A-Z]{4})[-_ .]?(\d{3})[. -]?(\d{2})(?!\d)')
FORMATS = {'.iso', '.zso', '.vcd'}
ART_TYPES = {'COV': (140, 200), 'COV2': (242, 344), 'ICO': (64, 64),
             'BG': (640, 480), 'SCR': (250, 188), 'SCR2': (250, 188),
             'LAB': (18, 240), 'LGO': (300, 125)}

class Cancelled(Exception): pass


def cancelled(event):
    if event is not None and event.is_set(): raise Cancelled('Operación cancelada; el original no se ha modificado.')


def normalize_id(value: str) -> str:
    m = ID_RE.search(value)
    return f'{m[1].upper()}_{m[2]}.{m[3]}' if m else ''


def require_id(value: str) -> str:
    result = normalize_id(value)
    if not result or result != value.upper(): raise ValueError('ID no válido; usa el formato SLES_123.45.')
    return result


def serial_key(value: str) -> str:
    return require_id(value).replace('_', '-').replace('.', '')


def game_database() -> dict:
    return json.loads((BASE/'assets/games.json').read_text(encoding='utf-8'))


@dataclass
class Game:
    path: Path
    root: Path
    title: str
    game_id: str = ''
    kind: str = 'ISO'
    media: str = 'DVD'
    size: int = 0
    region: str = ''
    id_source: str = ''
    issues: list[str] = field(default_factory=list)
    parts: list[Path] = field(default_factory=list)

    def art_path(self, kind='COV') -> Path | None:
        if not self.game_id: return None
        folder = directory(self.root, 'ART')
        for ext in ('.png', '.jpg', '.jpeg', '.PNG', '.JPG'):
            p = folder / f'{self.game_id}_{kind}{ext}'
            if p.is_file(): return p
        return None

    @property
    def cfg_path(self): return directory(self.root, 'CFG') / f'{require_id(self.game_id)}.cfg'
    @property
    def cheat_path(self): return directory(self.root, 'CHT') / f'{require_id(self.game_id)}.cht'


def directory(root: Path, name: str) -> Path:
    """Reuse existing case-insensitive OPL directories, without creating anything."""
    exact = root/name
    if exact.is_dir(): return exact
    try:
        for p in root.iterdir():
            if p.name.upper() == name and p.is_dir(): return p
    except OSError: pass
    return exact


class Lz4:
    def __init__(self):
        lib = ctypes.util.find_library('lz4')
        if not lib: raise RuntimeError('Falta liblz4 en este equipo.')
        self.lib = ctypes.CDLL(lib)
        self.lib.LZ4_compressBound.argtypes = [ctypes.c_int]
        self.lib.LZ4_compressBound.restype = ctypes.c_int
        self.lib.LZ4_compress_default.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_int, ctypes.c_int]
        self.lib.LZ4_compress_default.restype = ctypes.c_int
        self.lib.LZ4_decompress_safe.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_int, ctypes.c_int]
        self.lib.LZ4_decompress_safe.restype = ctypes.c_int
    def compress(self, data):
        bound = self.lib.LZ4_compressBound(len(data)); out = ctypes.create_string_buffer(bound)
        n = self.lib.LZ4_compress_default(data, out, len(data), bound)
        if n <= 0: raise ValueError('Error al comprimir un bloque LZ4.')
        return out.raw[:n]
    def decompress(self, data, expected):
        out = ctypes.create_string_buffer(expected)
        n = self.lib.LZ4_decompress_safe(data, out, len(data), expected)
        if n != expected: raise ValueError('Bloque ZSO dañado o tamaño LZ4 incorrecto.')
        return out.raw[:n]


class DiscImage:
    """Random read access to ISO or ZISO v1, bounded by declared image size."""
    def __init__(self, path):
        self.file = open(path, 'rb'); self.physical_size = os.fstat(self.file.fileno()).st_size
        self.size = self.physical_size; self.zso = False
        try:
            header = self.file.read(24)
            if header[:4] == b'ZISO':
                magic, hs, total, block, ver, align = struct.unpack('<4sIQIBB2x', header)
                if hs != 24 or ver != 1 or block != 2048 or align > 16 or total == 0:
                    raise ValueError('Cabecera ZSO no compatible (se admite ZISO v1, sectores de 2048 bytes).')
                self.size, self.block, self.align = total, block, align
                self.count = math.ceil(total/block)
                if self.count > 16000000 or 24+4*(self.count+1) > self.physical_size:
                    raise ValueError('Índice ZSO fuera de los límites del archivo.')
                self.lz4 = Lz4(); self.zso = True
            elif str(path).lower().endswith('.zso'):
                raise ValueError('El archivo .zso no contiene una cabecera ZISO.')
        except Exception:
            self.file.close(); raise
    def __enter__(self): return self
    def __exit__(self, *args): self.file.close()
    def _block(self, i):
        self.file.seek(24+4*i)
        a,b = struct.unpack('<II', self.file.read(8))
        start = (a & 0x7fffffff) << self.align
        end = (b & 0x7fffffff) << self.align
        expected = min(self.block, self.size-i*self.block)
        if not 24+4*(self.count+1) <= start < end <= self.physical_size or end-start > 131072:
            raise ValueError('Índice ZSO dañado.')
        self.file.seek(start); data = self.file.read(end-start)
        if a & 0x80000000:
            if len(data) < expected: raise ValueError('Bloque ZSO incompleto.')
            return data[:expected]
        # LZ4 alignment padding is outside the compressed stream. Up to (2**align)-1 trailing bytes.
        for padding in range(min((1 << self.align), len(data))):
            try: return self.lz4.decompress(data[:len(data)-padding], expected)
            except ValueError: pass
        raise ValueError('No se ha podido leer un bloque comprimido ZSO.')
    def read(self, offset, length):
        if offset < 0 or length < 0 or offset+length > self.size: raise ValueError('Lectura fuera del disco.')
        if not self.zso:
            self.file.seek(offset); b = self.file.read(length)
            if len(b) != length: raise ValueError('Imagen truncada.')
            return b
        if not length: return b''
        first = offset//self.block; last = (offset+length-1)//self.block
        data = b''.join(self._block(i) for i in range(first,last+1))
        start = offset % self.block
        return data[start:start+length]


def iso_id(image: DiscImage) -> str:
    pvd = None
    for sector in range(16,48):
        if (sector+1)*2048 > image.size: break
        data = image.read(sector*2048,2048)
        if data[1:6] != b'CD001': continue
        if data[0] == 1: pvd=data; break
        if data[0] == 255: break
    if pvd is None: raise ValueError('No se encuentra un sistema de archivos ISO9660 válido.')
    extent = struct.unpack_from('<I',pvd,158)[0]; size = struct.unpack_from('<I',pvd,166)[0]
    if not 0 < size <= 8*1024*1024: raise ValueError('Directorio raíz ISO9660 no válido.')
    root = image.read(extent*2048,size); pos=0
    while pos < len(root):
        n=root[pos]
        if not n: pos=(pos//2048+1)*2048; continue
        if n<34 or pos+n>len(root): raise ValueError('Directorio ISO9660 dañado.')
        rec=root[pos:pos+n]; name=rec[33:33+rec[32]].decode('ascii','replace').split(';')[0].upper()
        if name == 'SYSTEM.CNF':
            start=struct.unpack_from('<I',rec,2)[0]*2048; length=struct.unpack_from('<I',rec,10)[0]
            if length>65536: raise ValueError('SYSTEM.CNF demasiado grande.')
            cnf=image.read(start,length).decode('ascii','replace')
            boot=re.search(r'(?im)^\s*BOOT2?\s*=\s*([^\r\n]+)',cnf)
            if boot:
                value=normalize_id(boot[1])
                if value: return value
            raise ValueError('SYSTEM.CNF no contiene un ID de arranque reconocible.')
        pos+=n
    raise ValueError('No se encuentra SYSTEM.CNF en la imagen.')


def inspect_game(path: Path, root: Path, db: dict) -> Game:
    named_id=normalize_id(path.stem)
    title=re.sub(r'(?i)^[A-Z]{4}[-_ .]?\d{3}[. -]?\d{2}[. _-]*','',path.stem).strip() or path.stem
    g=Game(path,root,title,named_id,path.suffix[1:].upper(),path.parent.name.upper() if path.parent.name.upper() in ('CD','DVD','POPS') else 'DVD',path.stat().st_size)
    if g.kind in ('ISO','ZSO'):
        try:
            with DiscImage(path) as image: disk_id=iso_id(image)
            if named_id and named_id != disk_id: g.issues.append(f'El nombre dice {named_id}, pero el disco contiene {disk_id}.')
            g.game_id=disk_id;g.id_source='SYSTEM.CNF'
        except (OSError,ValueError,struct.error,RuntimeError) as e:
            g.issues.append(str(e)); g.id_source='Nombre de archivo' if named_id else 'Sin identificar'
    else:
        g.media='POPS';g.id_source='Nombre de archivo' if named_id else 'Sin identificar'
        if not named_id: g.issues.append('VCD sin ID en el nombre; no se ha inferido un ID del contenido.')
    if g.game_id:
        info=db.get(serial_key(g.game_id),{})
        g.region=info.get('region','')
        if info.get('title'): g.title=info['title']
    return g


def scan_library(root: Path, progress=None, cancel=None):
    root=root.resolve(strict=True)
    if not root.is_dir(): raise ValueError('Selecciona una carpeta, no un archivo.')
    folders=[root]
    for name in ('DVD','CD','POPS'):
        p=directory(root,name)
        if p.is_dir() and p!=root: folders.append(p)
    paths=[]; warnings=[]
    for folder in folders:
        try: paths.extend(p for p in folder.iterdir() if p.is_file() and not p.is_symlink() and p.suffix.lower() in FORMATS)
        except OSError as e: warnings.append(str(e))
    paths=sorted(set(paths),key=lambda p:p.name.casefold()); db=game_database(); games=[]
    # If user selects DVD/CD/POPS itself, use its parent for ART/CFG/CHT.
    opl_root=root.parent if root.name.upper() in ('DVD','CD','POPS') else root
    for i,p in enumerate(paths):
        cancelled(cancel)
        try: games.append(inspect_game(p,opl_root,db))
        except OSError as e: warnings.append(f'{p.name}: {e}')
        if progress: progress(i+1,len(paths),p.name)
    ul=root/'ul.cfg'
    if ul.is_file():
        data=ul.read_bytes()
        if len(data)%64: warnings.append('ul.cfg tiene registros incompletos; se han omitido los bytes finales.')
        for offset in range(0,len(data)-63,64):
            cancelled(cancel); r=data[offset:offset+64]
            title=r[:32].split(b'\0')[0].decode('utf-8','replace'); gid=normalize_id(r[35:47].decode('ascii','replace'))
            if r[32:35] != b'ul.': warnings.append(f'ul.cfg: cabecera no válida en el registro {offset//64+1}.');continue
            if not gid: warnings.append(f'ul.cfg: ID no válido en el registro {offset//64+1}.');continue
            parts=sorted(root.glob(f'ul.*.{gid}.*'))
            issues=[] if len(parts)==r[47] else [f'Partes UL encontradas: {len(parts)}; esperadas: {r[47]}.']
            if len({p.name.split('.')[1] for p in parts}) > 1:
                issues.append('Varias series UL comparten este ID; no se mezclarán sus partes.');parts=[]
            elif parts and [p.name.rsplit('.',1)[-1].lower() for p in parts] != [f'{i:02x}' for i in range(r[47])]:
                issues.append('La secuencia de partes UL no está completa.')
            games.append(Game(ul,root,title,gid,'UL','DVD' if r[48]==0x14 else 'CD',sum(p.stat().st_size for p in parts),db.get(serial_key(gid),{}).get('region',''),'ul.cfg',issues,parts))
    return games,warnings


def publish_new(source: Path, dest: Path):
    """Atomic publication without clobbering on ext4, FAT and exFAT."""
    try: os.link(source,dest)
    except OSError as e:
        if e.errno not in (1,95): raise
        libc=ctypes.CDLL(None,use_errno=True);fn=getattr(libc,'renameat2',None)
        if fn is None: raise RuntimeError('El volumen no admite publicación segura sin sobrescritura.') from e
        fn.argtypes=[ctypes.c_int,ctypes.c_char_p,ctypes.c_int,ctypes.c_char_p,ctypes.c_uint]
        if fn(-100,os.fsencode(source),-100,os.fsencode(dest),1):
            err=ctypes.get_errno();raise OSError(err,os.strerror(err),str(dest))


def atomic_bytes(path: Path, data: bytes, overwrite=True):
    path.parent.mkdir(parents=True,exist_ok=True)
    if path.is_symlink(): raise ValueError('No se escribirá a través de un enlace simbólico.')
    fd,name=tempfile.mkstemp(prefix='.'+path.name+'.',suffix='.tmp',dir=path.parent)
    tmp=Path(name)
    try:
        with os.fdopen(fd,'wb') as f:f.write(data);f.flush();os.fsync(f.fileno())
        if overwrite: os.replace(tmp,path)
        else: publish_new(tmp,path)
    finally: tmp.unlink(missing_ok=True)


def backup_text(path: Path, text: str, expected: bytes | None = None):
    # Refuse to silently overwrite changes made by OPL/another editor since opening.
    current=path.read_bytes() if path.exists() else None
    if current != expected: raise ValueError('El archivo ha cambiado desde que se abrió. Ciérralo y vuelve a abrirlo.')
    if path.is_symlink(): raise ValueError('No se modifica un archivo enlazado.')
    if current is not None: atomic_bytes(path.with_suffix(path.suffix+'.bak'), current)
    atomic_bytes(path,text.replace('\r\n','\n').replace('\r','\n').replace('\n','\r\n').encode('utf-8'))


def rename_game(game: Game, title: str, include_id=True):
    if game.kind=='UL': raise ValueError('Renombrar UL no está implementado; ul.cfg permanece intacto.')
    title=title.strip()
    if not title or title in ('.','..') or any(c in title for c in '<>:"/\\|?*') or any(ord(c)<32 for c in title):
        raise ValueError('El título está vacío o contiene caracteres no compatibles con OPL.')
    # OPL legacy filenames have a 32-character title field.
    if include_id and len(title.encode('utf-8'))>32: raise ValueError('El nombre clásico de OPL admite hasta 32 bytes de título. Acórtalo o usa nombre moderno.')
    prefix=f'{require_id(game.game_id)}.' if include_id else ''
    target=game.path.with_name(prefix+title+game.path.suffix.lower())
    if target == game.path: return target
    # link/unlink is a no-clobber rename on the same volume; fallback is intentionally not destructive.
    try: os.link(game.path,target)
    except OSError as e:
        if e.errno in (1,95):
            # FAT/exFAT lack hardlinks: Linux renameat2(RENAME_NOREPLACE) is atomic and no-clobber.
            libc=ctypes.CDLL(None,use_errno=True)
            fn=getattr(libc,'renameat2',None)
            if fn is None: raise RuntimeError('Este sistema no admite renombrado seguro sin sobrescritura.') from e
            fn.argtypes=[ctypes.c_int,ctypes.c_char_p,ctypes.c_int,ctypes.c_char_p,ctypes.c_uint]
            if fn(-100,os.fsencode(game.path),-100,os.fsencode(target),1)!=0:
                errno=ctypes.get_errno();raise OSError(errno,os.strerror(errno),str(target))
            return target
        raise
    else: game.path.unlink()
    return target


def hash_game(game: Game, progress=None,cancel=None):
    files=game.parts if game.kind=='UL' else [game.path]
    if not files: raise ValueError('No hay partes del juego para verificar.')
    if game.kind=='UL' and game.issues: raise ValueError('Resuelve los avisos de las partes UL antes de calcular su huella.')
    h=hashlib.sha256();total=sum(p.stat().st_size for p in files);done=0
    for path in files:
        with path.open('rb') as f:
            while True:
                cancelled(cancel);data=f.read(4*1024*1024)
                if not data:break
                h.update(data);done+=len(data)
                if progress:progress(done,total,path.name)
    return h.hexdigest()


def export_csv(games,path):
    out=io.StringIO(newline='');writer=csv.writer(out)
    writer.writerow(['Título','ID','Formato','Medio','Región','Bytes','Carátula','CFG','Ruta','Avisos'])
    def safe(value):
        s=str(value)
        return "'"+s if s.startswith(('=','+','-','@','\t','\r')) else s
    for g in games:
        writer.writerow([safe(g.title),g.game_id,g.kind,g.media,g.region,g.size,'Sí' if g.art_path() else 'No',
                         'Sí' if g.game_id and g.cfg_path.exists() else 'No',safe(g.path),' | '.join(g.issues)])
    atomic_bytes(Path(path),out.getvalue().encode('utf-8-sig'))


def import_art(game: Game, source: Path, kind='COV', overwrite=False):
    from PIL import Image,ImageOps
    if kind not in ART_TYPES: raise ValueError('Tipo de imagen no admitido.')
    require_id(game.game_id)
    if game.art_path(kind) and not overwrite: raise FileExistsError('Ya hay una imagen de este tipo.')
    with Image.open(source) as im:
        im=ImageOps.exif_transpose(im).convert('RGBA')
        im=ImageOps.contain(im,ART_TYPES[kind],Image.Resampling.LANCZOS)
        canvas=Image.new('RGBA',ART_TYPES[kind],(0,0,0,0))
        canvas.paste(im,((canvas.width-im.width)//2,(canvas.height-im.height)//2),im)
        out=io.BytesIO();canvas=canvas.quantize(colors=256,method=Image.Quantize.FASTOCTREE);canvas.save(out,'PNG')
    dest=directory(game.root,'ART')/f'{game.game_id}_{kind}.png'
    if dest.exists() and overwrite:atomic_bytes(dest.with_suffix('.png.bak'),dest.read_bytes())
    atomic_bytes(dest,out.getvalue(),overwrite=overwrite)
    return dest


def download_cover(game: Game,progress=None,cancel=None):
    require_id(game.game_id)
    if game.art_path(): return 'Ya tenía carátula'
    url=f'https://raw.githubusercontent.com/xlenore/ps2-covers/main/covers/default/{serial_key(game.game_id)}.jpg'
    cancelled(cancel)
    req=urllib.request.Request(url,headers={'User-Agent':'OPL-Manager-Linux/1.0'})
    with urllib.request.urlopen(req,timeout=20) as response:
        data=response.read(12*1024*1024+1)
    if len(data)>12*1024*1024:raise ValueError('La imagen remota supera el límite de 12 MiB.')
    cancelled(cancel)
    with tempfile.NamedTemporaryFile(suffix='.jpg') as f:
        f.write(data);f.flush();dest=import_art(game,Path(f.name))
    return str(dest)


def convert_image(source: Path,dest: Path,progress=None,cancel=None):
    source=source.resolve(strict=True);dest=dest.absolute()
    if source == dest or dest.exists():raise FileExistsError('El destino ya existe; nunca se sobrescribe una imagen.')
    to_zso=source.suffix.lower()=='.iso' and dest.suffix.lower()=='.zso'
    to_iso=source.suffix.lower()=='.zso' and dest.suffix.lower()=='.iso'
    if not (to_zso or to_iso):raise ValueError('Conversión admitida: ISO ↔ ZSO.')
    dest.parent.mkdir(parents=True,exist_ok=True)
    fd,name=tempfile.mkstemp(prefix='.'+dest.name+'.',suffix='.part',dir=dest.parent);tmp=Path(name)
    try:
        with os.fdopen(fd,'w+b') as out,DiscImage(source) as image:
            if to_iso:
                for offset in range(0,image.size,4*1024*1024):
                    cancelled(cancel);out.write(image.read(offset,min(4*1024*1024,image.size-offset)))
                    if progress:progress(min(offset+4*1024*1024,image.size),image.size,source.name)
            else:
                if not image.size or image.size%2048:raise ValueError('La ISO debe tener un número entero de sectores de 2048 bytes.')
                lz4=Lz4();count=image.size//2048;align=max(0,((image.size+24+4*(count+1))>>31).bit_length())
                index=[];out.write(struct.pack('<4sIQIBB2x',b'ZISO',24,image.size,2048,1,align));out.seek(24+4*(count+1))
                for i in range(count):
                    cancelled(cancel);raw=image.read(i*2048,2048);compressed=lz4.compress(raw);plain=len(compressed)>=len(raw)
                    pad=(-out.tell())% (1<<align)
                    if pad:out.write(b'\0'*pad)
                    value=out.tell()>>align
                    if value>=0x80000000:raise ValueError('Imagen demasiado grande para el índice ZSO.')
                    index.append(value | (0x80000000 if plain else 0));out.write(raw if plain else compressed)
                    if progress and i%512==0:progress(i*2048,image.size,source.name)
                pad=(-out.tell())%(1<<align)
                if pad:out.write(b'\0'*pad)
                index.append(out.tell()>>align);out.seek(24)
                # chunks avoid enormous argument lists for large images.
                for start in range(0,len(index),65536):
                    group=index[start:start+65536];out.write(struct.pack('<'+'I'*len(group),*group))
            out.flush();os.fsync(out.fileno())
        cancelled(cancel)
        # The output is only made visible when complete. No replacement of an existing destination.
        publish_new(tmp,dest)
        if progress:progress(image.size,image.size,dest.name)
        return dest
    finally:tmp.unlink(missing_ok=True)
