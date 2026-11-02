"""Create a formatted PS2 VMC (512-byte pages, no ECC/spare), without Wine.

Filesystem layout interoperates with Open PS2 Loader pc/genvmc, jimmikaelkael.
No existing memory card or game is modified.
"""
from datetime import datetime,timezone
import os
from pathlib import Path
import struct
import tempfile
from .core import cancelled,publish_new

SIZES=(8,16,32,64)

def create_vmc(path,size_mb=8,progress=None,cancel=None):
    path=Path(path)
    if size_mb not in SIZES:raise ValueError('Tamaños VMC admitidos: 8, 16, 32 o 64 MiB.')
    if path.exists() or path.is_symlink():raise FileExistsError('La VMC ya existe; nunca se sobrescribe.')
    clusters=size_mb*1024;fat_len=(clusters+255)//256;ifc_len=(fat_len+255)//256
    fat_start=8+ifc_len;alloc=fat_start+fat_len;alloc_end=clusters-16-alloc
    header=bytearray(384)
    magic=b'Sony PS2 Memory Card Format 1.2.0.0';header[:len(magic)]=magic
    struct.pack_into('<hHHHIIIIII',header,40,512,2,16,0,clusters,alloc,alloc_end,0,clusters//8-1,clusters//8-2)
    struct.pack_into('<32I',header,80,*([8+i for i in range(ifc_len)]+[0xffffffff]*(32-ifc_len)))
    struct.pack_into('<32I',header,208,*([0xffffffff]*32))
    struct.pack_into('<BBHIIIiIIIIIIi',header,336,2,0x2b,0,1024,256,8,1,0,0,0,(clusters//1000)*1000+1,0,0,-1)
    path.parent.mkdir(parents=True,exist_ok=True)
    fd,name=tempfile.mkstemp(prefix='.'+path.name+'.',suffix='.tmp',dir=path.parent);tmp=Path(name)
    try:
        with os.fdopen(fd,'w+b') as f:
            chunk=b'\xff'*(1024*1024)
            for mb in range(size_mb):
                cancelled(cancel);f.write(chunk)
                if progress:progress(mb+1,size_mb,'Preparando VMC')
            indirect=bytearray(ifc_len*1024)
            struct.pack_into('<'+'I'*fat_len,indirect,0,*range(fat_start,alloc))
            f.seek(8*1024);f.write(indirect)
            fat=bytearray(((alloc_end+255)//256)*1024)
            struct.pack_into('<'+'I'*alloc_end,fat,0,*([0x7fffffff]*alloc_end));struct.pack_into('<I',fat,0,0xffffffff)
            f.seek(fat_start*1024);f.write(fat)
            now=datetime.now(timezone.utc);stamp=struct.pack('<6BH',0,now.second,now.minute,now.hour,now.day,now.month,now.year)
            root=bytearray(1024)
            for offset,mode,title in [(0,0x8427,b'.'),(512,0xa426,b'..')]:
                struct.pack_into('<HHI',root,offset,mode,0,2);root[offset+8:offset+16]=stamp;root[offset+24:offset+32]=stamp
                root[offset+64:offset+64+len(title)]=title
            f.seek(alloc*1024);f.write(root);f.seek(0);f.write(header+b'\xff'*(1024-len(header)));f.flush();os.fsync(f.fileno())
        cancelled(cancel);publish_new(tmp,path);return path
    finally:tmp.unlink(missing_ok=True)
