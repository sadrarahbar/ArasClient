"""Install, launch and uninstall the actual setup executable on the Windows runner."""
from pathlib import Path
import os
import subprocess
import tempfile

ROOT=Path(__file__).resolve().parent
OUT=ROOT.parent/'artifacts/windows'


def main():
    setup=next(OUT.glob('*-Setup.exe'))
    with tempfile.TemporaryDirectory() as d:
        temp=Path(d);destination=temp/'Installed Tesla Vpn';uninstaller=None
        try:
            subprocess.run([str(setup),'/VERYSILENT','/SUPPRESSMSGBOXES','/NORESTART',f'/DIR={destination}'],
                check=True,timeout=120)
            exe=destination/'TeslaVpn.exe'
            if not exe.is_file():raise RuntimeError('Installer did not copy the application.')
            uninstaller=destination/'unins000.exe'
            subprocess.run([str(exe),'--state-root',str(temp/'private-state'),
                '--screenshot',str(temp/'installed.png')],check=True,timeout=30,
                env=dict(os.environ,QT_QPA_PLATFORM='offscreen'))
            if not (temp/'installed.png').is_file():raise RuntimeError('Installed application did not render.')
            print('Setup installs successfully and installed EXE renders its UI')
        finally:
            if uninstaller and uninstaller.exists():
                subprocess.run([str(uninstaller),'/VERYSILENT','/SUPPRESSMSGBOXES','/NORESTART'],check=True,timeout=120)
        if (destination/'TeslaVpn.exe').exists():raise RuntimeError('Uninstaller left the application executable behind.')
        print('Uninstall succeeds and removes the installed application')

if __name__=='__main__':main()
