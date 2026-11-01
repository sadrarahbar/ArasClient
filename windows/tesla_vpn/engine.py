"""Qt event-driven connection lifecycle and end-to-end HTTPS verification."""
import json
import os
import re
from pathlib import Path
import socket
import time
from PyQt6.QtCore import QObject, QProcess, QProcessEnvironment, QTimer, QUrl, pyqtSignal
from PyQt6.QtNetwork import QNetworkAccessManager, QNetworkProxy, QNetworkRequest, QNetworkReply
from .profiles import private_write
from .runtime import command, free_port, prepare
from .system_proxy import SystemProxy


class Engine(QObject):
    changed = pyqtSignal()
    notice = pyqtSignal(str)
    def __init__(self, root: Path):
        super().__init__()
        self.root = root
        self.state = "idle"
        self.message = ""
        self.testing = False
        self.latency = None
        self.exit_country = None
        self.proxy_country = None
        self.mode = "tun"
        self.core = None
        self.bridge = None
        self.reply = None
        self.error_after_stop = ""
        self.buffer = b""
        self.proxy = SystemProxy(root)
        self.net = QNetworkAccessManager(self)
        self.poller = QTimer(self); self.poller.setInterval(500); self.poller.timeout.connect(self._poll)
        self.probe_timer = QTimer(self); self.probe_timer.setSingleShot(True)
        self.probe_timer.timeout.connect(lambda: self.reply.abort() if self.reply else None)

    @property
    def busy(self): return self.state in ("starting", "checking", "stopping")

    def start(self, profile, mode):
        if self.state not in ("idle", "error"): return
        self.mode = mode; self.error_after_stop = ""; self.latency = None
        self.exit_country = self.proxy_country = None
        self.port, self.http_port = free_port(), free_port()
        while self.http_port == self.port: self.http_port = free_port()
        try:
            plan = prepare(profile, self.port, self.root)
            request = self.root / "session.json"
            private_write(request, json.dumps({"plan": plan.encode(), "port": self.port, "mode": mode}).encode())
            self.core = QProcess(self)
            self.core.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
            self.core.readyReadStandardOutput.connect(self._read_output)
            self.core.errorOccurred.connect(self._process_error)
            self.core.finished.connect(self._finished)
            self.buffer = b""
            self._set("starting", "Authorizing system VPN…" if mode == "tun" else "Starting tunnel…")
            args = command("--tun-helper" if mode == "tun" else "--backend-run", str(request))
            self.core.start(args[0], args[1:])
            self.deadline = time.monotonic() + 240
            self.poller.start()
        except (ValueError, OSError) as e:
            self._set("error", str(e))

    def _poll(self):
        if self.state != "starting": self.poller.stop(); return
        if time.monotonic() > self.deadline:
            self._fail("Connection timed out. Check the profile or try another network."); return
        try:
            with socket.create_connection(("127.0.0.1", self.port), timeout=.05) as s:
                s.settimeout(.05); s.sendall(b"\x05\x01\x00")
                if s.recv(2) != b"\x05\x00": return
        except OSError: return
        self.poller.stop(); self._set("checking", "Checking internet through the tunnel…")
        self._probe("startup", direct=False)

    def _read_output(self):
        self.buffer += bytes(self.core.readAllStandardOutput())
        while b"\n" in self.buffer:
            line, self.buffer = self.buffer.split(b"\n", 1)
            # Only our supervisor emits JSON; native logs never enter the GUI.
            try: event = json.loads(line).get("event")
            except (ValueError, AttributeError): continue
            if event == "backend-started": self.message = "Finding a working endpoint…"; self.changed.emit()
            elif event == "tun-ready": self._probe("startup-direct", direct=True)
            elif event in ("tun-setup-failed", "tun-failed", "tun-routing-failed", "admin-required", "backend-failed"):
                messages = {"admin-required": "System VPN requires administrator permission.",
                    "tun-routing-failed": "System traffic did not enter Tesla VPN. Disconnect other VPNs and retry.",
                    "backend-failed": "The VPN core stopped. Check the imported configuration."}
                self._fail(messages.get(event, "Could not start Windows TUN. Check administrator permission and the bundled Wintun driver."))


    def _process_error(self, error):
        if error == QProcess.ProcessError.FailedToStart:
            self._fail("Could not start the VPN helper. Check the installation and Windows security settings.")

    def _finished(self, *_):
        if self.state == "stopping": self._stopped()
        elif self.state not in ("idle", "error"):
            self._fail("The tunnel stopped or administrator authorization was cancelled.")

    def _probe(self, purpose, direct=False, attempt=0):
        if self.reply is not None: return
        self.testing = True; self.changed.emit()
        proxy = QNetworkProxy(QNetworkProxy.ProxyType.NoProxy) if direct else QNetworkProxy(
            QNetworkProxy.ProxyType.Socks5Proxy, "127.0.0.1", self.port)
        self.net.clearConnectionCache()
        self.net.setProxy(proxy)
        urls = ["https://www.cloudflare.com/cdn-cgi/trace", "https://www.gstatic.com/generate_204"]
        request = QNetworkRequest(QUrl(urls[attempt])); request.setTransferTimeout(15000)
        request.setRawHeader(b"User-Agent", b"TeslaVpn/1.0")
        self.probe_started = time.monotonic()
        reply = self.net.get(request); self.reply = reply
        self.probe_timer.start(16000)
        reply.finished.connect(lambda: self._probe_done(reply, purpose, direct, attempt))

    def _probe_done(self, reply, purpose, direct, attempt):
        self.probe_timer.stop()
        status = reply.attribute(QNetworkRequest.Attribute.HttpStatusCodeAttribute)
        ok = reply.error() == QNetworkReply.NetworkError.NoError and status in (200, 204)
        elapsed = round((time.monotonic() - self.probe_started) * 1000)
        body = bytes(reply.readAll()).decode("utf-8", "replace")
        match = re.search(r"^loc=([A-Z]{2})$", body, re.MULTILINE) if attempt == 0 and ok else None
        country = match.group(1) if match else None
        self.reply = None; reply.deleteLater()
        if self.state == "stopping": self.testing = False; return
        if not ok and attempt == 0:
            self._probe(purpose, direct, 1); return
        self.testing = False
        if not ok:
            if purpose == "manual":
                self.message = "Internet check failed. The tunnel is still running."; self.changed.emit()
            else: self._fail("The tunnel answered, but HTTPS internet access could not be verified.")
            return
        if purpose == "startup-direct" and country and self.proxy_country and country != self.proxy_country:
            self._fail("System VPN exit differs from the proxy exit. Disconnect other VPNs and retry.")
            return
        self.exit_country = country
        self.latency = elapsed
        result_message = f"Connection succeeded in {elapsed} ms" + (f" · Exit: {country}" if country else "")
        if purpose == "startup" and self.mode == "tun":
            self.proxy_country = country
            self.message = "Applying system VPN routes…"; self.changed.emit()
            self.core.write(b"enable\n")
        elif purpose.startswith("startup"):
            try:
                self._start_bridge()
                if self.mode == "proxy": self.proxy.activate(self.port, self.http_port)
                self._set("connected", result_message)
            except Exception:
                self._fail("Could not apply proxy settings. Previous settings will be restored.")
        else:
            self.message = result_message; self.changed.emit()

    def _start_bridge(self):
        self.bridge = QProcess(self)
        args = command("--http-bridge", str(self.port), str(self.http_port))
        self.bridge.start(args[0], args[1:])
        if not self.bridge.waitForStarted(2000): raise OSError("HTTP proxy failed")
        self.bridge.finished.connect(lambda *_: self._fail("The local proxy stopped.") if self.state == "connected" else None)

    def test(self):
        if self.state != "connected" or self.testing: return
        self.message = "Testing…"; self._probe("manual", direct=self.mode == "tun")

    def _fail(self, message):
        self.error_after_stop = message
        self.stop()

    def stop(self):
        if self.state == "stopping": return
        self.poller.stop()
        self._set("stopping", "Restoring network settings…")
        if self.reply is not None: self.reply.abort()
        self.testing = False
        try: self.proxy.restore()
        except Exception: self.notice.emit("Previous proxy settings could not be restored. Recovery will be retried at next launch.")
        if self.bridge is not None:
            self.bridge.terminate(); self.bridge.waitForFinished(1000); self.bridge.kill(); self.bridge = None
        if self.core is not None and self.core.state() != QProcess.ProcessState.NotRunning:
            self.core.write(b"stop\n"); self.core.closeWriteChannel()
            QTimer.singleShot(10000, self._force_stop_user_core)
        else: self._stopped()

    def _force_stop_user_core(self):
        if self.state == "stopping" and self.core is not None:
            self.core.kill()  # Closing its Job Object kills every descendant too.

    def _stopped(self):
        message, self.error_after_stop = self.error_after_stop, ""
        self._set("error" if message else "idle", message or "Disconnected")

    def _set(self, state, message):
        self.state = state; self.message = message
        try:
            private_write(self.root / "status.json", json.dumps({"state": state, "mode": self.mode,
                "message": message, "updated": time.time()}).encode())
        except OSError:
            pass  # Diagnostics must never prevent network cleanup.
        self.changed.emit()
