#!/usr/bin/env python3
"""Entry point, including non-GUI helpers so packaged builds require no Python install."""
import argparse
import asyncio
import json
import os
from pathlib import Path
import sys


def main():
    parser = argparse.ArgumentParser(description="Tesla Vpn for Linux")
    parser.add_argument("--tun-helper", metavar="SESSION")
    parser.add_argument("--backend-run", metavar="SESSION")
    parser.add_argument("--http-bridge", nargs=2, type=int, metavar=("SOCKS_PORT", "HTTP_PORT"))
    parser.add_argument("--screenshot", metavar="PNG", help=argparse.SUPPRESS)
    parser.add_argument("--profile", metavar="FILE", help="Import a configuration file on startup")
    parser.add_argument("--connect", action="store_true", help="Connect the saved profile on startup")
    parser.add_argument("--mode", choices=("tun", "proxy"), default="tun", help="Startup connection mode")
    options = parser.parse_args()
    if options.tun_helper:
        from tesla_vpn.tun import main as helper
        return helper(options.tun_helper)
    if options.backend_run:
        plan = json.loads(Path(options.backend_run).read_text())["plan"]
        env = {k: v for k, v in os.environ.items() if not k.startswith("AETHER_") and k not in ("RUST_LOG", "LD_PRELOAD")}
        env.update(plan["env"])
        os.chdir(plan["cwd"]); os.setsid()
        import ctypes, signal
        ctypes.CDLL(None).prctl(1, signal.SIGINT, 0, 0, 0)
        os.execve(plan["argv"][0], plan["argv"], env)
    if options.http_bridge:
        import ctypes, signal
        ctypes.CDLL(None).prctl(1, signal.SIGTERM, 0, 0, 0)
        from tesla_vpn.http_bridge import serve
        asyncio.run(serve(*options.http_bridge)); return 0
    from PyQt6.QtCore import QLockFile, QTimer
    from PyQt6.QtWidgets import QApplication, QMessageBox
    from PyQt6.QtGui import QFont
    from tesla_vpn.runtime import state_root
    from tesla_vpn.ui import Window
    app = QApplication(sys.argv[:1]); app.setApplicationName("Tesla Vpn"); app.setDesktopFileName("tesla-vpn"); app.setFont(QFont("DejaVu Sans", 14))
    root = state_root(); root.mkdir(parents=True, mode=0o700, exist_ok=True); root.chmod(0o700)
    lock = QLockFile(str(root / "application.lock"))
    if not lock.tryLock(100): QMessageBox.information(None, "Tesla Vpn", "Tesla Vpn is already running."); return 0
    window = Window(root); app.setWindowIcon(window.windowIcon())
    if options.profile:
        window.import_text(Path(options.profile).read_text(encoding="utf-8-sig"))
    if options.mode == "proxy": window.proxy.setChecked(True)
    window.show()
    if options.connect and window.profile:
        QTimer.singleShot(0, lambda: window.engine.start(window.profile, options.mode))
    if options.screenshot:
        QTimer.singleShot(600, lambda: (window.grab().save(options.screenshot), app.quit()))
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
