#!/usr/bin/env python3
"""Entry point, including non-GUI helpers so packaged builds require no Python install."""
import argparse
import asyncio
import json
import os
from pathlib import Path
import sys


def main():
    parser = argparse.ArgumentParser(description="Tesla Vpn for Windows 10/11 x64")
    parser.add_argument("--tun-helper", metavar="SESSION")
    parser.add_argument("--backend-run", metavar="SESSION")
    parser.add_argument("--http-bridge", nargs=2, type=int, metavar=("SOCKS_PORT", "HTTP_PORT"))
    parser.add_argument("--screenshot", metavar="PNG", help=argparse.SUPPRESS)
    parser.add_argument("--profile", metavar="FILE", help="Import a configuration file on startup")
    parser.add_argument("--connect", action="store_true", help="Connect the saved profile on startup")
    parser.add_argument("--mode", choices=("tun", "proxy"), default="tun", help="Startup connection mode")
    parser.add_argument("--state-root", type=Path, help=argparse.SUPPRESS)
    parser.add_argument("--wait-parent", type=int, help=argparse.SUPPRESS)
    parser.add_argument("--restore-proxy", action="store_true", help=argparse.SUPPRESS)
    options = parser.parse_args()
    if options.tun_helper or options.backend_run or options.http_bridge:
        from tesla_vpn.win32 import helper_stdio
        helper_stdio()
    if options.wait_parent:
        from tesla_vpn.win32 import wait_for_parent
        wait_for_parent(options.wait_parent)
    if options.restore_proxy:
        from tesla_vpn.runtime import state_root
        from tesla_vpn.system_proxy import SystemProxy
        SystemProxy(options.state_root or state_root()).restore(); return 0
    if options.tun_helper:
        from tesla_vpn.tun import main as helper
        return helper(options.tun_helper)
    if options.backend_run:
        from tesla_vpn.tun import main as helper
        return helper(options.backend_run, with_tun=False)
    if options.http_bridge:
        import threading
        def parent_watch():
            for _ in sys.stdin: pass
            os._exit(0)
        threading.Thread(target=parent_watch, daemon=True).start()
        from tesla_vpn.http_bridge import serve
        asyncio.run(serve(*options.http_bridge)); return 0
    from PyQt6.QtCore import QLockFile, QTimer
    from PyQt6.QtWidgets import QApplication, QMessageBox
    from PyQt6.QtGui import QFont
    from tesla_vpn.runtime import state_root
    from tesla_vpn.ui import Window
    app = QApplication(sys.argv[:1]); app.setApplicationName("Tesla Vpn"); app.setDesktopFileName("tesla-vpn"); app.setFont(QFont("DejaVu Sans", 14))
    from tesla_vpn.win32 import supported_windows, private_directory, repair_account_permissions
    if sys.platform == "win32" and not supported_windows():
        QMessageBox.critical(None, "Tesla Vpn", "Windows 10 version 1809 or newer, 64-bit, is required."); return 1
    root = options.state_root or state_root()
    private_directory(root)
    lock = QLockFile(str(root / "application.lock"))
    if not lock.tryLock(100): QMessageBox.information(None, "Tesla Vpn", "Tesla Vpn is already running."); return 0
    repair_account_permissions(root)
    window = Window(root); app.setWindowIcon(window.windowIcon())
    if options.profile:
        window.import_text(Path(options.profile).read_text(encoding="utf-8-sig"))
    if options.mode == "proxy": window.proxy.setChecked(True)
    window.show()
    if options.connect and window.profile:
        QTimer.singleShot(0, window.toggle)
    if options.screenshot:
        QTimer.singleShot(600, lambda: (window.grab().save(options.screenshot), app.quit()))
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
