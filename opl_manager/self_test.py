"""Exercise shipped resources and UI using only a temporary library."""
def run():
    import hashlib, json, os, struct, tempfile
    from pathlib import Path
    from unittest.mock import patch
    from PIL import Image
    from PyQt6.QtWidgets import QApplication
    from . import __version__,ui
    from .core import game_database, inspect_game, convert_image, import_art
    from .games_index import generate_indexes
    from .vmc import create_vmc
    from .themes import THEMES
    def record(extent,size,name):
        length=33+len(name)+(len(name)%2==0);b=bytearray(length);b[0]=length
        struct.pack_into('<I',b,2,extent);struct.pack_into('>I',b,6,extent)
        struct.pack_into('<I',b,10,size);struct.pack_into('>I',b,14,size)
        b[28:32]=b'\x01\0\0\x01';b[32]=len(name);b[33:33+len(name)]=name
        return b
    app=QApplication.instance() or QApplication([])
    with tempfile.TemporaryDirectory(prefix='opl-manager-self-test-') as temp:
        root=Path(temp);(root/'DVD').mkdir();(root/'CD').mkdir()
        source=root/'DVD/test.iso';data=bytearray(64*2048)
        data[16*2048:16*2048+7]=b'\x01CD001\x01'
        data[16*2048+156:16*2048+190]=record(20,2048,b'\0')
        cnf=b'BOOT2 = cdrom0:\\SLES_526.78;1\r\nVER = 1.00\r\n'
        entry=record(21,len(cnf),b'SYSTEM.CNF;1');data[20*2048:20*2048+len(entry)]=entry
        data[21*2048:21*2048+len(cnf)]=cnf;source.write_bytes(data)
        digest=hashlib.sha256(data).hexdigest()
        game=inspect_game(source,root,game_database());assert game.game_id=='SLES_526.78'
        generate_indexes(root);assert (root/'DVD/games.bin').stat().st_size==92
        zso=root/'converted.zso';restored=root/'restored.iso'
        convert_image(source,zso);convert_image(zso,restored);assert restored.read_bytes()==data
        png=root/'cover.png';Image.new('RGB',(300,400),'purple').save(png)
        art=import_art(game,png);assert art.exists()
        vmc=root/'VMC/test.bin';create_vmc(vmc,8);assert vmc.stat().st_size==8*1024*1024
        with patch.object(ui,'CONFIG',root/'settings.json'):
            window=ui.MainWindow();window.show();app.processEvents()
            for theme in THEMES:
                window.apply_theme(theme);app.processEvents()
            window.apply_theme('ugm');assert ui.read_settings()['theme']=='ugm'
            window.close();app.processEvents()
        assert hashlib.sha256(source.read_bytes()).hexdigest()==digest
        result={'version':__version__,'database':len(game_database()),'checks':['ISO ID','92-byte index','LZ4 roundtrip','Pillow artwork','8 MiB VMC','Qt window','five themes','temporary settings','original preserved']}
        print(json.dumps(result))
    return 0
