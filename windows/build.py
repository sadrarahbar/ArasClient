"""Build on Windows; keep all installers/binaries out of git."""
import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import sys
import zipfile

ROOT = Path(__file__).resolve().parent
PROJECT = ROOT.parent


def main():
    if sys.platform != 'win32': raise SystemExit('Build the EXE on Windows (GitHub Actions), not on Linux.')
    subprocess.run([sys.executable,str(ROOT/'prepare_cores.py')],check=True)
    sys.path.insert(0,str(ROOT))
    from PyQt6.QtWidgets import QApplication
    from tesla_vpn.ui import app_icon
    from PIL import Image
    os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
    app = QApplication.instance() or QApplication([])
    build=ROOT/'build';build.mkdir(exist_ok=True)
    png=build/'icon.png';app_icon().pixmap(256,256).save(str(png))
    Image.open(png).save(build/'icon.ico',sizes=[(16,16),(32,32),(48,48),(256,256)])
    out=PROJECT/'artifacts/windows'
    subprocess.run([sys.executable,'-m','PyInstaller','--noconfirm','--clean','--onedir',
        '--console','--hide-console','hide-early','--name','TeslaVpn',
        '--icon',str(build/'icon.ico'),'--manifest',str(ROOT/'app.manifest'),
        '--version-file',str(ROOT/'version.txt'),'--distpath',str(out),
        '--workpath',str(build/'pyinstaller'),'--specpath',str(build),'--paths',str(ROOT),
        '--add-data',str(ROOT/'assets')+os.pathsep+'assets',
        '--add-data',str(ROOT/'cores')+os.pathsep+'cores',
        '--add-data',str(ROOT/'licenses')+os.pathsep+'licenses',
        '--exclude-module','PySide6','--exclude-module','PyQt5',str(ROOT/'main.py')],check=True)
    shutil.copy2(ROOT/'README.fa.md',out/'TeslaVpn/README.fa.md')
    zipname=out/'TeslaVpn-1.0.0-Windows-x64.zip'
    with zipfile.ZipFile(zipname,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for p in (out/'TeslaVpn').rglob('*'):
            if p.is_file():z.write(p,p.relative_to(out))
    (out/'SHA256SUMS').write_text(hashlib.sha256(zipname.read_bytes()).hexdigest()+'  '+zipname.name+'\n')
    print('Portable Windows package:',zipname)

if __name__=='__main__':main()
