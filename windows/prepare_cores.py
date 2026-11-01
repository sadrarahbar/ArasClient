#!/usr/bin/env python3
"""Download version- and SHA256-pinned official Windows x64 executables."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import urllib.request
import zipfile
import zlib

ROOT = Path(__file__).resolve().parent
PINNED = json.loads((ROOT / 'core-checksums.json').read_text(encoding='utf-8'))
SOURCES = {
    'aether': ('https://github.com/CluvexStudio/Aether/releases/download/v2.4.0/aether-windows-x86_64.zip',
        {'aether.exe':'aether.exe','pt/psiphon-tunnel-core.exe':'psiphon-tunnel-core.exe','pt/lyrebird.exe':'lyrebird.exe'}),
    'xray': ('https://github.com/XTLS/Xray-core/releases/download/v26.3.27/Xray-windows-64.zip',
        {n:n for n in ['xray.exe','geoip.dat','geosite.dat']}),
    'sing-box': ('https://github.com/SagerNet/sing-box/releases/download/v1.12.12/sing-box-1.12.12-windows-amd64.zip',
        {'sing-box-1.12.12-windows-amd64/sing-box.exe':'sing-box.exe'}),
    'wintun': ('https://www.wintun.net/builds/wintun-0.14.1.zip',{'wintun/bin/amd64/wintun.dll':'wintun.dll'}),
}


def digest(path):
    with path.open('rb') as f: return hashlib.file_digest(f,'sha256').hexdigest()


def main():
    cores = ROOT / 'cores'; cores.mkdir(exist_ok=True)
    cache = Path(os.environ.get('LOCALAPPDATA',str(Path.home()/'.cache'))) / 'TeslaVpn/downloads'
    cache.mkdir(parents=True,exist_ok=True)
    for name,(url,files) in SOURCES.items():
        if all((cores/n).is_file() and digest(cores/n)==PINNED['files'][n] for n in files.values()): continue
        archive = cache / (name+'-'+PINNED['archives'][name][:12]+'.zip')
        if not archive.exists() or digest(archive)!=PINNED['archives'][name]:
            temp=archive.with_suffix('.partial')
            print('Downloading official '+name,flush=True)
            with urllib.request.urlopen(url,timeout=120) as src,temp.open('wb') as dst: shutil.copyfileobj(src,dst)
            if digest(temp)!=PINNED['archives'][name]: temp.unlink();raise ValueError('Archive checksum mismatch: '+name)
            temp.replace(archive)
        with zipfile.ZipFile(archive) as z:
            for member,target in files.items():
                data=z.read(member)
                if hashlib.sha256(data).hexdigest()!=PINNED['files'][target]:raise ValueError('Core checksum mismatch: '+target)
                (cores/target).write_bytes(data)
    target=cores/'psiphon-servers.txt'
    if not target.exists() or digest(target)!=PINNED['files'][target.name]:
        data=json.loads(zlib.decompress((ROOT.parent/'app/src/main/assets/psiphon_servers.dat').read_bytes()))['data'].encode()
        target.write_bytes(data)
    for name,expected in PINNED['files'].items():
        if digest(cores/name)!=expected:raise ValueError('Invalid resource: '+name)
    print('All Windows native cores verified.')

if __name__=='__main__':main()
