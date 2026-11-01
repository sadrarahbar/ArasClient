"""Reversible GNOME/KDE proxy preferences, with crash recovery and no root access."""
import json
import os
from pathlib import Path
import shutil
import subprocess
from .profiles import private_write


def run(args):
    return subprocess.run(args, capture_output=True, text=True, check=True, timeout=5).stdout.strip()


class SystemProxy:
    KDE_KEYS = ["ProxyType", "httpProxy", "httpsProxy", "socksProxy", "NoProxyFor", "ReversedException"]
    GNOME_KEYS = [("org.gnome.system.proxy", "mode"), ("org.gnome.system.proxy", "ignore-hosts"),
                  ("org.gnome.system.proxy.http", "host"), ("org.gnome.system.proxy.http", "port"),
                  ("org.gnome.system.proxy.https", "host"), ("org.gnome.system.proxy.https", "port"),
                  ("org.gnome.system.proxy.socks", "host"), ("org.gnome.system.proxy.socks", "port")]

    def __init__(self, root: Path):
        self.backup = root / "proxy-recovery.json"

    def _snapshot_kde(self, socks_port, http_port):
        reader = shutil.which("kreadconfig6") or shutil.which("kreadconfig5")
        writer = shutil.which("kwriteconfig6") or shutil.which("kwriteconfig5")
        if not reader or not writer: raise ValueError("KDE proxy tools are missing.")
        old = {k: run([reader, "--file", "kioslaverc", "--group", "Proxy Settings", "--key", k,
                       "--default", "__TESLA_ABSENT__"]) for k in self.KDE_KEYS}
        # Publish the mode last, after every endpoint is ready.
        new = {"httpProxy": f"http://127.0.0.1 {http_port}", "httpsProxy": f"http://127.0.0.1 {http_port}",
               "socksProxy": f"socks://127.0.0.1 {socks_port}", "NoProxyFor": "localhost,127.0.0.1,::1",
               "ReversedException": "false", "ProxyType": "1"}
        return {"desktop": "kde", "reader": reader, "writer": writer, "old": old, "new": new}

    def _snapshot_gnome(self, socks_port, http_port):
        old = {f"{s}/{k}": run(["gsettings", "get", s, k]) for s, k in self.GNOME_KEYS}
        new = {f"{s}/{k}": ("['localhost', '127.0.0.1', '::1']" if k == "ignore-hosts" else
               "'127.0.0.1'" if k == "host" else str(socks_port if s.endswith("socks") else http_port))
               for s, k in self.GNOME_KEYS if k != "mode"}
        new["org.gnome.system.proxy/mode"] = "'manual'"
        return {"desktop": "gnome", "old": old, "new": new}

    def activate(self, socks_port, http_port):
        if self.backup.exists(): self.restore()
        desktop = os.environ.get("XDG_CURRENT_DESKTOP", "").lower()
        targets = []
        if "kde" in desktop: targets.append(self._snapshot_kde(socks_port, http_port))
        gtk_desktop = any(d in desktop for d in ["gnome", "ubuntu", "cinnamon", "unity"])
        if "kde" not in desktop and not gtk_desktop:
            raise ValueError("Automatic system proxy supports KDE and GNOME. Use TUN on this desktop.")
        # Firefox/GTK read GSettings even on Plasma; KIO settings alone do not cover them.
        if shutil.which("gsettings"):
            schemas = set(run(["gsettings", "list-schemas"]).splitlines())
            required = {s for s, _ in self.GNOME_KEYS}
            if required <= schemas: targets.append(self._snapshot_gnome(socks_port, http_port))
            elif gtk_desktop: raise ValueError("GNOME proxy schemas are missing.")
        elif gtk_desktop:
            raise ValueError("gsettings is missing.")
        data = {"version": 2, "targets": targets}
        private_write(self.backup, json.dumps(data).encode())
        try:
            for target in targets:
                for key, value in target["new"].items(): self._write(target, key, value)
                self._reload(target)
        except Exception:
            self.restore()
            raise ValueError("Could not enable system proxy. Previous preferences were restored.") from None

    def restore(self):
        if not self.backup.exists(): return
        data = json.loads(self.backup.read_text())
        # Accept snapshots made by older builds too. Keep recovery on partial failure.
        targets = data["targets"] if data.get("version") == 2 else [data]
        for target in reversed(targets):
            for key, value in target["old"].items():
                if self._read(target, key) == target["new"][key]: self._write(target, key, value)
            self._reload(target)
        self.backup.unlink()

    def _read(self, d, key):
        if d["desktop"] == "kde":
            return run([d["reader"], "--file", "kioslaverc", "--group", "Proxy Settings", "--key", key, "--default", "__TESLA_ABSENT__"])
        schema, key = key.split("/")
        return run(["gsettings", "get", schema, key])

    def _write(self, d, key, value):
        if d["desktop"] == "kde":
            args = [d["writer"], "--file", "kioslaverc", "--group", "Proxy Settings", "--key", key]
            run(args + (["--delete"] if value == "__TESLA_ABSENT__" else [value]))
        else:
            schema, key = key.split("/"); run(["gsettings", "set", schema, key, value])

    def _reload(self, d):
        if d["desktop"] == "kde":
            subprocess.run(["dbus-send", "--session", "--type=signal", "/KIO/Scheduler",
                            "org.kde.KIO.Scheduler.reparseSlaveConfiguration", "string:"], capture_output=True, timeout=5)
