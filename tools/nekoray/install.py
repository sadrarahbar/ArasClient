#!/usr/bin/env python3
"""Install the pinned Linux Aether binary and its Nekoray custom-core launcher."""
import hashlib
from pathlib import Path
import platform
import shutil
import sys
import tarfile
import tempfile
import urllib.request
import json
import zlib


def main():
    if sys.version_info < (3, 11) or platform.system() != "Linux":
        raise SystemExit("Linux with Python 3.11 or newer is required")
    arch = {"x86_64": "x86_64", "aarch64": "aarch64"}.get(platform.machine())
    if arch is None:
        raise SystemExit("Unsupported CPU architecture")
    root = Path.home() / ".local/share/aras-nekoray"
    root.mkdir(parents=True, mode=0o700, exist_ok=True)
    root.chmod(0o700)
    asset = f"aether-linux-{arch}-musl.tar.gz"
    url = f"https://github.com/CluvexStudio/Aether/releases/download/v2.4.0/{asset}"
    cache = root / "downloads"
    cache.mkdir(exist_ok=True)
    archive = cache / "aether.tar.gz"
    checksum = cache / "aether.sha256"
    if not archive.is_file() or not checksum.is_file():
        print("Downloading Aether v2.4.0 and its SHA-256 checksum...", flush=True)
        urllib.request.urlretrieve(url, archive)
        urllib.request.urlretrieve(url + ".sha256", checksum)
    expected = checksum.read_text().split()[0].lower()
    with archive.open("rb") as stream:
        actual = hashlib.file_digest(stream, "sha256").hexdigest()
    if actual != expected:
        raise SystemExit("Checksum mismatch; remove cached downloads and retry")
    with tempfile.TemporaryDirectory(dir=root) as temp:
        with tarfile.open(archive) as source:
            members = [m for m in source.getmembers() if m.isfile() and Path(m.name).name == "aether"]
            if len(members) != 1:
                raise SystemExit("Archive does not contain one Aether executable")
            with source.extractfile(members[0]) as src, (Path(temp) / "aether").open("wb") as out:
                shutil.copyfileobj(src, out)
            pt = next((m for m in source.getmembers() if m.isfile() and Path(m.name).name == "psiphon-tunnel-core"), None)
            if pt is not None:
                with source.extractfile(pt) as src, (Path(temp) / "psiphon-tunnel-core").open("wb") as out:
                    shutil.copyfileobj(src, out)
                (Path(temp) / "psiphon-tunnel-core").chmod(0o755)
                (Path(temp) / "psiphon-tunnel-core").replace(root / "psiphon-tunnel-core")
        (Path(temp) / "aether").chmod(0o755)
        (Path(temp) / "aether").replace(root / "aether")
    shutil.copyfile(Path(__file__).with_name("aras-aether.py"), root / "aras-aether")
    (root / "aras-aether").chmod(0o755)
    bootstrap = Path(__file__).resolve().parents[2] / "app/src/main/assets/psiphon_servers.dat"
    if bootstrap.is_file():
        # The same public bootstrap asset bundled with the Android application.
        entries = json.loads(zlib.decompress(bootstrap.read_bytes()))["data"]
        if not isinstance(entries, str) or not entries.strip():
            raise SystemExit("Invalid bundled Psiphon bootstrap list")
        (root / "psiphon-servers.txt").write_text(entries)
    print(f"Installed. In Nekoray > Preferences > Basic Settings > Core > Extra Core, add:\nName: aras-aether\nPath: {root / 'aras-aether'}")


if __name__ == "__main__":
    main()
