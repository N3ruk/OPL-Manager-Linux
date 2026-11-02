#!/usr/bin/env python3
"""Build DEB, portable AppImage and a curated public source archive, without sudo."""
import argparse,hashlib,json,os,platform,re,shutil,subprocess,sys,tarfile,tempfile,urllib.request
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from opl_manager import __version__ as VERSION
from prepare_rootfs import BASE,sandbox
CACHE=ROOT/'.cache';BUILD=ROOT/'build';DIST=ROOT/'dist'
DOCS=('USAGE.md','BUILD.md','VERIFICATION.md','screenshot.png','es')
PUBLIC=('opl_manager','assets','packaging','tests','licenses','opl-manager-linux','README.md','README_ES.md','LICENSE','THIRD_PARTY.md','CHANGELOG.md','CHANGELOG_ES.md','VERSION','.gitignore','.github')
def run(argv,**kw):return subprocess.run([str(x) for x in argv],check=True,**kw)
def fetch(spec):
 p=CACHE/spec['file']
 if not p.exists():
  with urllib.request.urlopen(urllib.request.Request(spec['url'],headers={'User-Agent':'OPL-Manager-Linux-builder'})) as source,p.open('wb') as dst:shutil.copyfileobj(source,dst)
 if hashlib.sha256(p.read_bytes()).hexdigest()!=spec['sha256']:raise RuntimeError('SHA256 mismatch: '+p.name)
 return p
def copy_item(src,dst):
 if src.is_dir():shutil.copytree(src,dst,ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
 else:shutil.copy2(src,dst)
def payload(dst):
 dst.mkdir(parents=True)
 for n in ('opl_manager','assets','licenses','opl-manager-linux','README.md','README_ES.md','LICENSE','THIRD_PARTY.md','CHANGELOG.md','CHANGELOG_ES.md','VERSION'):copy_item(ROOT/n,dst/n)
 docs=dst/'docs';docs.mkdir()
 for n in DOCS:copy_item(ROOT/'docs'/n,docs/n)
def source_archive():
 target=DIST/f'opl-manager-linux-{VERSION}-source.tar.gz'
 with tarfile.open(target,'w:gz') as tf:
  for n in PUBLIC:
   tf.add(ROOT/n,arcname=f'opl-manager-linux/{n}',filter=lambda x:None if '__pycache__' in x.name or x.name.endswith('.pyc') else x)
  for n in DOCS:tf.add(ROOT/'docs'/n,arcname=f'opl-manager-linux/docs/{n}')
 return target
def desktop(stage):
 d=stage/'usr/share/applications';d.mkdir(parents=True);shutil.copy2(ROOT/'packaging/opl-manager-linux.desktop',d)
 d=stage/'usr/share/icons/hicolor/scalable/apps';d.mkdir(parents=True);shutil.copy2(ROOT/'assets/opl-manager.svg',d/'opl-manager-linux.svg')
def deb():
 stage=BUILD/'deb'
 if stage.exists():shutil.rmtree(stage)
 appdir=BUILD/'OPL-Manager-Linux.AppDir'
 app=stage/'opt/opl-manager-linux';app.parent.mkdir(parents=True)
 shutil.copytree(appdir,app,symlinks=True,ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
 desktop(stage)
 bindir=stage/'usr/bin';bindir.mkdir(parents=True);(bindir/'opl-manager-linux').symlink_to('/opt/opl-manager-linux/AppRun')
 doc=stage/'usr/share/doc/opl-manager-linux';doc.mkdir(parents=True);shutil.copy2(ROOT/'LICENSE',doc/'copyright')
 control=stage/'DEBIAN';control.mkdir()
 size=sum(p.stat().st_size for p in stage.rglob('*') if p.is_file())//1024
 (control/'control').write_text(f'''Package: opl-manager-linux
Version: {VERSION}
Architecture: amd64
Maintainer: N3ruk <noreply@github.com>
Section: games
Priority: optional
Depends: libc6 (>= 2.35)
Installed-Size: {size}
Homepage: https://github.com/N3ruk/OPL-Manager-Linux
Description: Native Linux library manager for Open PS2 Loader
 Independent Linux client inspired by OPL Manager for Windows.
 Includes Python, Qt, Pillow, LZ4 and support libraries.
 Manage game libraries, artwork, CFG/CHT, VMC and CD/DVD indexes.
''')
 out=DIST/f'opl-manager-linux_{VERSION}_amd64.deb';pending=out.with_suffix('.deb.pending');run(['dpkg-deb','-Zzstd','-z10','--root-owner-group','--build',stage,pending]);pending.replace(out);return out
def appimage():
 if platform.machine()!='x86_64':raise RuntimeError('AppImage build requires x86_64')
 specs=json.loads((ROOT/'packaging/toolchain-lock.json').read_text());tools={k:fetch(v) for k,v in specs.items()}
 if not (CACHE/'python/.extraction-complete').exists():
  with tarfile.open(tools['python']) as tf:
   for m in tf.getmembers():
    target=(CACHE/m.name).resolve()
    if not target.is_relative_to(CACHE.resolve()):raise RuntimeError('Unsafe tar path')
    if m.issym() or m.islnk():
     link=((target.parent if m.issym() else CACHE)/m.linkname).resolve()
     if not link.is_relative_to(CACHE.resolve()):raise RuntimeError('Unsafe tar link')
  # GNU tar handles safe relative terminfo symlinks consistently on Python 3.10+.
  run(['tar','--no-same-owner','-xzf',tools['python'],'-C',CACHE])
  (CACHE/'python/.extraction-complete').touch()
 wheels=CACHE/'wheels';wheels.mkdir(exist_ok=True)
 run([CACHE/'python/bin/python3','-m','pip','download','--require-hashes','--dest',wheels,'-r',ROOT/'packaging/requirements-appimage.txt'])
 if not (BASE/'usr/bin/ldd').exists():run([sys.executable,ROOT/'packaging/prepare_rootfs.py'])
 stage=BUILD/'OPL-Manager-Linux.AppDir'
 if stage.exists():shutil.rmtree(stage)
 payload(stage/'usr/share/opl-manager-linux');desktop(stage)
 py=stage/'usr/python';shutil.copytree(CACHE/'python',py,ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
 run([py/'bin/python3','-m','pip','install','--no-index','--find-links',wheels,'--require-hashes','-r',ROOT/'packaging/requirements-appimage.txt'])
 site=py/'lib/python3.12/site-packages';qt=site/'PyQt6/Qt6'
 modules={'QtCore','QtGui','QtWidgets','QtNetwork','QtDBus','QtOpenGL','QtOpenGLWidgets','QtSvg','QtSvgWidgets','QtTest','sip'}
 libs={'Core','Gui','Widgets','Network','DBus','OpenGL','OpenGLWidgets','Svg','SvgWidgets','Test','XcbQpa','WaylandClient','WaylandEglClientHwIntegration','WaylandCompositor','WaylandGlobal','WlShellIntegration'}
 for f in (site/'PyQt6').glob('*.so'):
  if f.name.split('.')[0] not in modules:f.unlink()
 for f in (qt/'lib').glob('libQt6*.so.6'):
  if f.name[len('libQt6'):-len('.so.6')] not in libs:f.unlink()
 keep={'platforms','imageformats','iconengines','wayland-decoration-client','wayland-graphics-integration-client','wayland-shell-integration'}
 for f in (qt/'plugins').iterdir():
  if f.name not in keep:shutil.rmtree(f)
 for f in (qt/'plugins').rglob('*qpdf*'):f.unlink()
 for f in (qt/'plugins/platforms').glob('*'):
  if f.name not in {'libqxcb.so','libqoffscreen.so','libqminimal.so','libqwayland-generic.so','libqwayland-egl.so'}:f.unlink()
 for name in ('qml','translations','qsci'):
  if (qt/name).exists():shutil.rmtree(qt/name)
 for f in site.iterdir():
  if f.name.startswith(('pip','setuptools','pkg_resources','_distutils')):
   shutil.rmtree(f) if f.is_dir() else f.unlink()
 for n in ('include','share/man'):
  if (py/n).exists():shutil.rmtree(py/n)
 for f in (py/'bin').iterdir():
  if f.name.startswith(('pip','idle','pydoc','2to3')):f.unlink()
 dest=stage/'usr/lib';dest.mkdir(parents=True,exist_ok=True)
 # Resolve every retained ELF dependency against Ubuntu 22.04, never host libraries.
 elfs=[str(Path('/src')/f.relative_to(ROOT)) for f in stage.rglob('*') if f.is_file() and ('.so' in f.name or f.name=='python3.12')]
 code='''import subprocess,sys
for f in sys.argv[1:]:
 p=subprocess.run(['ldd',f],capture_output=True,text=True)
 for line in p.stdout.splitlines():
  if 'not found' in line: print('MISSING '+f+' '+line,flush=True)
  elif '=>' in line:
   s=line.split('=>',1)[1].strip().split()[0]
   if s.startswith('/'):print(s,flush=True)
'''
 # The build root needs no Python: use the bundled interpreter within the namespace.
 result=subprocess.run(sandbox(['/src/.cache/python/bin/python3','-c',code,*elfs]),check=True,capture_output=True,text=True,env=dict(os.environ,LD_LIBRARY_PATH='/src/build/OPL-Manager-Linux.AppDir/usr/python/lib:/src/build/OPL-Manager-Linux.AppDir/usr/python/lib/python3.12/site-packages/PyQt6/Qt6/lib:/src/build/OPL-Manager-Linux.AppDir/usr/python/lib/python3.12/site-packages/pillow.libs'))
 missing=[x for x in result.stdout.splitlines() if x.startswith('MISSING')]
 if missing:raise RuntimeError('\n'.join(missing[:30]))
 excludes=re.compile(r'^(ld-linux|libc\.|libm\.|libpthread\.|libdl\.|librt\.|libutil\.|libresolv\.|libanl\.)')
 for value in sorted(set(result.stdout.splitlines())):
  path=Path(value)
  if not value.startswith('/src/') and not excludes.match(path.name):shutil.copy2(BASE/value.lstrip('/'),dest/path.name)
 shutil.copy2(BASE/'usr/lib/x86_64-linux-gnu/liblz4.so.1',dest/'liblz4.so.1')
 fonts=stage/'usr/share/fonts';shutil.copytree(BASE/'usr/share/fonts/truetype/dejavu',fonts)
 app=stage/'usr/share/opl-manager-linux'
 (app/'fonts.conf').write_text('<?xml version="1.0"?><!DOCTYPE fontconfig SYSTEM "fonts.dtd"><fontconfig><dir prefix="relative">../fonts</dir><cachedir prefix="xdg">fontconfig</cachedir></fontconfig>\n')
 shutil.copy2(BASE/'etc/ssl/certs/ca-certificates.crt',app/'ca-certificates.crt')
 notices=app/'licenses/ubuntu';notices.mkdir(parents=True)
 for f in (BASE/'usr/share/doc').glob('*/copyright'):shutil.copy2(f,notices/(f.parent.name+'.copyright'))
 shutil.copy2(ROOT/'packaging/AppRun',stage/'AppRun');(stage/'AppRun').chmod(0o755)
 shutil.copy2(ROOT/'packaging/opl-manager-linux.desktop',stage)
 shutil.copy2(ROOT/'assets/opl-manager.svg',stage/'opl-manager-linux.svg');(stage/'.DirIcon').symlink_to('opl-manager-linux.svg')
 (stage/'usr/bin').mkdir();(stage/'usr/bin/opl-manager-linux').symlink_to('../../AppRun')
 for name in ('appimagetool','runtime'):tools[name].chmod(0o755)
 out=DIST/f'OPL-Manager-Linux-{VERSION}-x86_64.AppImage'
 run([tools['appimagetool'],'--appimage-extract-and-run','--no-appstream','--runtime-file',tools['runtime'],'--comp','zstd','--mksquashfs-opt','-processors','--mksquashfs-opt','2',stage,out],env=dict(os.environ,ARCH='x86_64',SOURCE_DATE_EPOCH='1793577600'))
 out.chmod(0o755);return out
if __name__=='__main__':
 for p in (CACHE,BUILD,DIST):p.mkdir(exist_ok=True)
 outputs=[appimage(),deb(),source_archive()]
 (DIST/'SHA256SUMS').write_text(''.join(hashlib.sha256(p.read_bytes()).hexdigest()+'  '+p.name+'\n' for p in outputs))
 print(json.dumps({p.name:p.stat().st_size for p in outputs}))
