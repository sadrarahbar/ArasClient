# Windowed PE subsystem: neither the GUI nor helper invocations allocate a console.
from pathlib import Path
root = Path(SPECPATH)
a = Analysis(
    [str(root / 'main.py')], pathex=[str(root)], binaries=[],
    datas=[(str(root / name), name) for name in ['assets', 'cores', 'licenses']],
    hiddenimports=['PyQt6.QtSvg'], excludes=['PySide6', 'PyQt5'], noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, [], exclude_binaries=True, name='TeslaVpn',
    debug=False, bootloader_ignore_signals=False, strip=False, upx=False,
    console=False,
    icon=str(root / 'build/icon.ico'), version=str(root / 'version.txt'),
    manifest=str(root / 'app.manifest'),
)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name='TeslaVpn')
