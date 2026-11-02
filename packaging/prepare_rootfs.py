#!/usr/bin/env python3
"""Prepare an isolated Ubuntu 22.04 build/test root, never the host system."""
from pathlib import Path
import hashlib, shutil, subprocess, urllib.request
ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'.cache/rootfs'
URL='https://cdimage.ubuntu.com/ubuntu-base/releases/22.04/release/ubuntu-base-22.04.5-base-amd64.tar.gz'
SHA='242cd8898b33ea806ef5f13b1076ed7c76f9f989d18384452f7166692438ff1a'
PACKAGES='libglib2.0-0 libwayland-client0 libwayland-cursor0 libwayland-egl1 libdrm2 libgbm1 libgl1 libegl1 libxkbcommon0 libxkbcommon-x11-0 libxcb-cursor0 libxcb-icccm4 libxcb-image0 libxcb-keysyms1 libxcb-randr0 libxcb-render-util0 libxcb-shape0 libxcb-sync1 libxcb-xfixes0 libxcb-xinerama0 libxcb-xkb1 libxcb-util1 libdbus-1-3 libfontconfig1 libfreetype6 libx11-xcb1 libxrender1 libxi6 libsm6 libice6 liblz4-1 fonts-dejavu-core binutils xvfb xauth ca-certificates'.split()
def sandbox(argv):
 return ['bwrap','--bind',str(BASE),'/', '--bind',str(ROOT),'/src','--dev','/dev','--proc','/proc','--unshare-user','--uid','0','--gid','0','--chdir','/src','--setenv','HOME','/tmp/opl-build-home','--setenv','LANG','C.UTF-8','--setenv','PATH','/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin',*argv]
def main():
 archive=ROOT/'.cache/ubuntu-base.tar.gz';archive.parent.mkdir(exist_ok=True)
 if not archive.exists():urllib.request.urlretrieve(URL,archive)
 if hashlib.sha256(archive.read_bytes()).hexdigest()!=SHA:raise SystemExit('Ubuntu Base SHA256 mismatch')
 if not (BASE/'bin/bash').exists():
  BASE.mkdir(parents=True,exist_ok=True);subprocess.run(['tar','--no-same-owner','-xzf',str(archive),'-C',str(BASE)],check=True)
 resolver=BASE/'etc/resolv.conf'
 if resolver.is_symlink():resolver.unlink()
 resolver.write_bytes(Path('/etc/resolv.conf').read_bytes())
 cert=BASE/'etc/ssl/certs/ca-certificates.crt';cert.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile('/etc/ssl/certs/ca-certificates.crt',cert)
 sources=BASE/'etc/apt/sources.list';sources.write_text(sources.read_text().replace('http://','https://'))
 (BASE/'etc/apt/apt.conf.d/00rootless').write_text('APT::Sandbox::User "root";\n')
 (BASE/'usr/local/share/fonts').mkdir(parents=True,exist_ok=True)
 subprocess.run(sandbox(['/bin/bash','-ec','export DEBIAN_FRONTEND=noninteractive; apt-get update; apt-get install -y --no-install-recommends '+' '.join(PACKAGES)]),check=True)
if __name__=='__main__':main()
