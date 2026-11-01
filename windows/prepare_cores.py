#!/usr/bin/env python3
"""Fetch pinned official Linux x86_64 cores; verify every installed resource's SHA-256."""
import hashlib
import json
from pathlib import Path
import platform
import shutil
import tarfile
import urllib.request
import zipfile
import zlib

ROOT = Path(__file__).resolve().parent
CORES = ROOT / 'cores'
PINNED = json.loads((ROOT / 'core-checksums.json').read_text())


def digest(path):
    with path.open('rb') as f: return hashlib.file_digest(f, 'sha256').hexdigest()


def install(name, data):
    if hashlib.sha256(data).hexdigest() != PINNED[name]: raise SystemExit('Checksum mismatch: ' + name)
    target = CORES / name; target.write_bytes(data)
    target.chmod(0o644 if name.endswith(('.txt', '.dat')) else 0o755)


def fetch(url, name):
    cache = Path.home() / '.cache/tesla-vpn/downloads'; cache.mkdir(parents=True, exist_ok=True)
    target = cache / name
    if not target.exists():
        print('Downloading ' + name, flush=True)
        temp = target.with_suffix('.partial')
        with urllib.request.urlopen(url, timeout=120) as src, temp.open('wb') as dst: shutil.copyfileobj(src, dst)
        temp.replace(target)
    return target


def main():
    if platform.machine() != 'x86_64' or platform.system() != 'Linux':
        raise SystemExit('This pinned build currently targets Linux x86_64.')
    CORES.mkdir(exist_ok=True)
    # Reuse verified local installs when present, without ever copying credentials.
    hints = {'aether': Path.home()/'.local/share/aras-nekoray/aether',
             'psiphon-tunnel-core': Path.home()/'.local/share/aras-nekoray/psiphon-tunnel-core',
             'psiphon-servers.txt': Path.home()/'.local/share/aras-nekoray/psiphon-servers.txt',
             'xray': Path.home()/'.local/share/aras-v2box/xray', 'sing-box': Path('/opt/nekoray/nekobox_core')}
    for name, hint in hints.items():
        if not (CORES/name).exists() and hint.is_file() and digest(hint) == PINNED[name]: install(name, hint.read_bytes())
    missing = lambda n: not (CORES/n).is_file() or digest(CORES/n) != PINNED[n]
    if any(missing(n) for n in ['aether', 'psiphon-tunnel-core']):
        archive = fetch('https://github.com/CluvexStudio/Aether/releases/download/v2.4.0/aether-linux-x86_64-musl.tar.gz','aether-v2.4.0.tar.gz')
        with tarfile.open(archive) as z:
            for name in ['aether', 'psiphon-tunnel-core']:
                member = next(x for x in z.getmembers() if x.isfile() and Path(x.name).name == name)
                install(name, z.extractfile(member).read())
    if any(missing(n) for n in ['xray','geoip.dat','geosite.dat']):
        archive = fetch('https://github.com/XTLS/Xray-core/releases/download/v26.3.27/Xray-linux-64.zip','xray-v26.3.27.zip')
        with zipfile.ZipFile(archive) as z:
            for name in ['xray','geoip.dat','geosite.dat']: install(name, z.read(name))
    if missing('sing-box'):
        archive = fetch('https://github.com/MatsuriDayo/nekoray/releases/download/4.0.1/nekoray-4.0.1-2024-12-12-linux64.zip','nekoray-v4.0.1.zip')
        with zipfile.ZipFile(archive) as z:
            name = next(n for n in z.namelist() if Path(n).name == 'nekobox_core')
            install('sing-box', z.read(name))
    if missing('psiphon-servers.txt'):
        asset = ROOT.parent/'app/src/main/assets/psiphon_servers.dat'
        install('psiphon-servers.txt',json.loads(zlib.decompress(asset.read_bytes()))['data'].encode())
    for name in PINNED:
        if missing(name): raise SystemExit('Invalid core resource: ' + name)
    print('All native cores verified.')

if __name__ == '__main__': main()
