"""Extra native equivalents for Windows batch tools and disc checksums."""
import hashlib
import zlib
from .core import cancelled

def game_hashes(game,progress=None,cancel=None):
    files=game.parts if game.kind=='UL' else [game.path]
    if not files or (game.kind=='UL' and game.issues):raise ValueError('No se pueden leer partes UL incompletas o ambiguas.')
    hashes={name:hashlib.new(name) for name in ('md5','sha1','sha256')};crc=0;done=0;total=sum(p.stat().st_size for p in files)
    for path in files:
        with path.open('rb') as stream:
            while True:
                cancelled(cancel);data=stream.read(4*1024*1024)
                if not data:break
                for h in hashes.values():h.update(data)
                crc=zlib.crc32(data,crc);done+=len(data)
                if progress:progress(done,total,path.name)
    return {'CRC32':f'{crc:08X}',**{k.upper():h.hexdigest() for k,h in hashes.items()}}
