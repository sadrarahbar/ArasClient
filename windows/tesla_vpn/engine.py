"""Nonblocking Qt connection lifecycle; file/WinINET operations use a serial worker."""
import json
import re
from pathlib import Path
import time
from PyQt6.QtCore import QObject, QProcess, QTimer, QUrl, pyqtSignal
from PyQt6.QtNetwork import QAbstractSocket, QTcpSocket, QNetworkAccessManager, QNetworkProxy, QNetworkRequest, QNetworkReply
from .profiles import private_write
from .runtime import command, free_port, prepare
from .system_proxy import SystemProxy
from .tasks import Tasks


class Engine(QObject):
    changed = pyqtSignal()
    notice = pyqtSignal(str)
    permission_required = pyqtSignal()

    def __init__(self, root: Path):
        super().__init__()
        self.root = root
        self.state = 'idle'; self.message = ''; self.testing = False
        self.latency = self.exit_country = self.proxy_country = None
        self.mode = 'tun'; self.core = self.bridge = self.reply = None
        self.error_after_stop = ''; self.buffer = b''
        self.proxy = SystemProxy(root); self.tasks = Tasks(self)
        self.epoch = 0; self.restore_pending = False
        self.socks_check = None; self.bridge_buffer = b''; self.pending_result = None
        self.net = QNetworkAccessManager(self)
        self.poller = QTimer(self); self.poller.setInterval(500); self.poller.timeout.connect(self._poll)
        self.probe_timer = QTimer(self); self.probe_timer.setSingleShot(True)
        self.probe_timer.timeout.connect(lambda: self.reply.abort() if self.reply else None)
        self.bridge_timer = QTimer(self); self.bridge_timer.setSingleShot(True)
        self.bridge_timer.timeout.connect(lambda: self._fail('The local HTTP proxy did not become ready.') if self.state == 'checking' else None)
        self.result_timer = QTimer(self); self.result_timer.setSingleShot(True)
        self.result_timer.setInterval(5000); self.result_timer.timeout.connect(self._clear_test_result)

    @property
    def busy(self): return self.state in ('starting', 'checking', 'stopping')

    def start(self, profile, mode):
        if self.state not in ('idle', 'error'): return
        self.epoch += 1; epoch = self.epoch
        self.mode = mode; self.error_after_stop = ''; self.latency = None
        self.exit_country = self.proxy_country = None
        self.pending_result = None; self.core = self.bridge = None
        self.port, self.http_port = free_port(), free_port()
        while self.http_port == self.port: self.http_port = free_port()
        self._set('starting', 'Authorizing system VPN…' if mode == 'tun' else 'Starting tunnel…')
        def prepare_request():
            plan = prepare(profile, self.port, self.root)
            request = self.root / 'session.json'
            private_write(request, json.dumps({'plan': plan.encode(), 'port': self.port, 'mode': mode}).encode())
            return request
        def ready(request, error):
            if epoch != self.epoch or self.state != 'starting': return
            if error:
                if isinstance(error, PermissionError):
                    self._fail('Windows denied access to saved account files. Administrator permission is needed once to repair access.')
                    self.permission_required.emit()
                else: self._fail(str(error))
                return
            proc = QProcess(self); self.core = proc
            proc.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
            proc.readyReadStandardOutput.connect(lambda: self._read_output(proc))
            proc.errorOccurred.connect(lambda e: self._process_error(proc, e))
            proc.finished.connect(lambda *_: self._finished(proc))
            self.buffer = b''
            args = command('--tun-helper' if mode == 'tun' else '--backend-run', str(request))
            self.deadline = time.monotonic() + 240
            proc.start(args[0], args[1:]); self.poller.start()
        self.tasks.submit(prepare_request, ready)

    def _dispose_socks(self, sock):
        if self.socks_check is not sock: return
        self.socks_check = None
        sock.abort(); sock.deleteLater()

    def _poll(self):
        if self.state != 'starting': self.poller.stop(); return
        if time.monotonic() > self.deadline:
            self._fail('Connection timed out. Check the profile or try another network.'); return
        if self.socks_check is not None: return
        sock = QTcpSocket(self); self.socks_check = sock
        sock.setProxy(QNetworkProxy(QNetworkProxy.ProxyType.NoProxy))
        sock.connected.connect(lambda: sock.write(b'\x05\x01\x00') if self.socks_check is sock else None)
        def received():
            if self.socks_check is not sock or sock.bytesAvailable() < 2: return
            ok = bytes(sock.read(2)) == b'\x05\x00'
            self._dispose_socks(sock)
            if ok and self.state == 'starting':
                self.poller.stop(); self._set('checking', 'Checking internet through the tunnel…')
                self._probe('startup', direct=False)
        sock.readyRead.connect(received)
        sock.errorOccurred.connect(lambda *_: self._dispose_socks(sock))
        QTimer.singleShot(400, lambda: self._dispose_socks(sock))
        sock.connectToHost('127.0.0.1', self.port)

    def _read_output(self, proc):
        if proc is not self.core: return
        self.buffer += bytes(proc.readAllStandardOutput())
        if self.state == 'stopping': self.buffer = b''; return
        while b'\n' in self.buffer:
            line, self.buffer = self.buffer.split(b'\n', 1)
            try: event = json.loads(line).get('event')
            except (ValueError, AttributeError): continue
            if event == 'backend-started': self.message = 'Finding a working endpoint…'; self.changed.emit()
            elif event == 'tun-ready': self._probe('startup-direct', direct=True)
            elif event in ('tun-setup-failed','tun-failed','tun-routing-failed','admin-required','backend-failed'):
                messages = {'admin-required': 'System VPN requires administrator permission.',
                    'tun-routing-failed': 'System traffic did not enter Tesla VPN. Disconnect other VPNs and retry.',
                    'backend-failed': 'The VPN core stopped. Check the imported configuration.'}
                self._fail(messages.get(event,'Could not start Windows TUN. Check administrator permission and the bundled Wintun driver.'))

    def _process_error(self, proc, error):
        if proc is not self.core: return
        if self.state == 'stopping': self._stopped()
        elif error == QProcess.ProcessError.FailedToStart:
            self._fail('Could not start the VPN helper. Check the installation and Windows security settings.')

    def _finished(self, proc):
        if proc is not self.core: return
        if self.state == 'stopping': self._stopped()
        elif self.state not in ('idle','error'):
            self._fail('The tunnel stopped or administrator authorization was cancelled.')

    def _probe(self, purpose, direct=False, attempt=0):
        if self.reply is not None: return
        self.testing = True; self.changed.emit()
        proxy = QNetworkProxy(QNetworkProxy.ProxyType.NoProxy) if direct else QNetworkProxy(QNetworkProxy.ProxyType.Socks5Proxy,'127.0.0.1',self.port)
        self.net.clearConnectionCache(); self.net.setProxy(proxy)
        urls = ['https://www.cloudflare.com/cdn-cgi/trace','https://www.gstatic.com/generate_204']
        request = QNetworkRequest(QUrl(urls[attempt])); request.setTransferTimeout(15000)
        request.setRawHeader(b'User-Agent', b'TeslaVpn/1.0')
        self.probe_started = time.monotonic()
        reply = self.net.get(request); self.reply = reply
        self.probe_timer.start(16000)
        epoch = self.epoch
        reply.finished.connect(lambda: self._probe_done(reply,purpose,direct,attempt,epoch))

    def _probe_done(self, reply, purpose, direct, attempt, epoch=None):
        if epoch is not None and epoch != self.epoch:
            reply.deleteLater(); return
        self.probe_timer.stop()
        status = reply.attribute(QNetworkRequest.Attribute.HttpStatusCodeAttribute)
        ok = reply.error() == QNetworkReply.NetworkError.NoError and status in (200,204)
        elapsed = round((time.monotonic()-self.probe_started)*1000)
        body = bytes(reply.readAll()).decode('utf-8','replace')
        match = re.search(r'^loc=([A-Z]{2})$',body,re.MULTILINE) if attempt == 0 and ok else None
        country = match.group(1) if match else None
        self.reply = None; reply.deleteLater()
        if self.state == 'stopping': self.testing = False; return
        if not ok and attempt == 0: self._probe(purpose,direct,1); return
        self.testing = False
        if not ok:
            if purpose == 'manual': self._show_test_result('Internet check failed. The tunnel is still running.')
            else: self._fail('The tunnel answered, but HTTPS internet access could not be verified.')
            return
        if purpose == 'startup-direct' and country and self.proxy_country and country != self.proxy_country:
            self._fail('System VPN exit differs from the proxy exit. Disconnect other VPNs and retry.'); return
        if country: self.exit_country = country
        self.latency = elapsed
        result = f'Connection succeeded in {elapsed} ms' + (f' · Exit: {country}' if country else '')
        if purpose == 'startup' and self.mode == 'tun':
            self.proxy_country = country; self.message = 'Applying system VPN routes…'; self.changed.emit()
            self.core.write(b'enable\n')
        elif purpose.startswith('startup'):
            self.pending_result = result
            self.message = 'Preparing local proxy…'; self.changed.emit()
            self._start_bridge()
        else: self._show_test_result(result)

    def _start_bridge(self):
        proc = QProcess(self); self.bridge = proc; self.bridge_buffer = b''
        proc.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        proc.readyReadStandardOutput.connect(lambda: self._bridge_output(proc))
        proc.finished.connect(lambda *_: self._bridge_finished(proc))
        proc.errorOccurred.connect(lambda e: self._bridge_error(proc,e))
        args = command('--http-bridge',str(self.port),str(self.http_port))
        self.bridge_timer.start(8000); proc.start(args[0],args[1:])

    def _bridge_output(self, proc):
        if proc is not self.bridge: return
        self.bridge_buffer += bytes(proc.readAllStandardOutput())
        while b'\n' in self.bridge_buffer:
            line,self.bridge_buffer = self.bridge_buffer.split(b'\n',1)
            try: ready = json.loads(line).get('event') == 'http-ready'
            except (ValueError,AttributeError): continue
            if ready: self._bridge_ready()

    def _bridge_ready(self):
        if self.state != 'checking' or self.pending_result is None: return
        self.bridge_timer.stop()
        result,self.pending_result = self.pending_result,None
        epoch = self.epoch
        def applied(_,error):
            if epoch != self.epoch or self.state != 'checking': return
            if error: self._fail('Could not apply proxy settings. Previous settings will be restored.')
            else: self._set('connected',result)
        if self.mode == 'proxy': self.tasks.submit(lambda: self.proxy.activate(self.port,self.http_port),applied)
        else: applied(None,None)

    def _bridge_finished(self, proc):
        if proc is not self.bridge: return
        if self.state == 'stopping': self._stopped()
        elif self.state in ('checking','connected'): self._fail('The local proxy stopped.')

    def _bridge_error(self, proc, error):
        if proc is self.bridge and error == QProcess.ProcessError.FailedToStart:
            if self.state == 'stopping': self._stopped()
            else: self._fail('Could not start the local HTTP proxy.')

    def _show_test_result(self, message):
        self.message = message
        self.result_timer.start(5000)
        self.changed.emit()

    def _clear_test_result(self):
        if self.state == 'connected' and not self.testing:
            self.message = ''
            self.changed.emit()

    def test(self):
        if self.state != 'connected' or self.testing: return
        self.result_timer.stop()
        self.message = 'Testing…'; self._probe('manual',direct=self.mode == 'tun')

    def _fail(self, message):
        self.error_after_stop = message; self.stop()

    def stop(self):
        if self.state == 'stopping': return
        self.epoch += 1; self.restore_pending = True
        self.poller.stop(); self.bridge_timer.stop(); self.pending_result = None
        if self.socks_check is not None: self._dispose_socks(self.socks_check)
        self._set('stopping','Restoring network settings…')
        self.probe_timer.stop()
        reply, self.reply = self.reply, None
        if reply is not None: reply.abort()
        self.testing = False
        def restored(_,error):
            self.restore_pending = False
            if error: self.notice.emit('Previous proxy settings could not be restored. Recovery will be retried at next launch.')
            self._stopped()
        # Serialized after activation: cancel while applying can never leave proxy on.
        self.tasks.submit(self.proxy.restore,restored)
        if self.bridge is not None and self.bridge.state() != QProcess.ProcessState.NotRunning:
            proc=self.bridge; proc.closeWriteChannel()  # EOF works for a windowless helper; WM_CLOSE does not.
            QTimer.singleShot(1000,lambda proc=proc: proc.kill() if self.bridge is proc and proc.state()!=QProcess.ProcessState.NotRunning else None)
        if self.core is not None and self.core.state() != QProcess.ProcessState.NotRunning:
            proc=self.core; proc.write(b'stop\n'); proc.closeWriteChannel()
            QTimer.singleShot(10000,lambda proc=proc: proc.kill() if self.core is proc and proc.state()!=QProcess.ProcessState.NotRunning else None)
        self._stopped()

    def _stopped(self):
        if self.state != 'stopping' or self.restore_pending: return
        if any(p is not None and p.state()!=QProcess.ProcessState.NotRunning for p in (self.core,self.bridge)): return
        message,self.error_after_stop = self.error_after_stop,''
        self._set('error' if message else 'idle',message or 'Disconnected')

    @property
    def session_seconds(self):
        if self.state != "connected" or self.connected_at is None: return 0
        return max(0, int(time.monotonic() - self.connected_at))

    def _set(self, state, message):
        if state == "connected" and self.state != "connected": self.connected_at = time.monotonic()
        elif state != "connected": self.connected_at = None
        self.state=state; self.message=message
        if state == 'connected': self.result_timer.start(5000)
        else: self.result_timer.stop()
        self.changed.emit()
        # Snapshot writes/fsync can be slow on Windows/antivirus; never paint-block.
        data=json.dumps({'state':state,'mode':self.mode,'message':message,'updated':time.time()}).encode()
        self.tasks.submit(lambda: private_write(self.root/'status.json',data),lambda *_: None)
