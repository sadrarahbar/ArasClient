import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from pathlib import Path
import sys,tempfile,time
import unittest
from unittest.mock import MagicMock
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from PyQt6.QtWidgets import QApplication
from PyQt6.QtNetwork import QNetworkReply
from PyQt6.QtTest import QTest
from tesla_vpn.engine import Engine
app=QApplication.instance() or QApplication([])

class Reply:
    def __init__(self,country):self.country=country
    def attribute(self,key):return 200
    def error(self):return QNetworkReply.NetworkError.NoError
    def readAll(self):return ('ip=not-logged\nloc='+self.country+'\n').encode()
    def deleteLater(self):pass

def drain(engine):
    deadline=time.monotonic()+5
    while engine.tasks.pending and time.monotonic()<deadline: QTest.qWait(10)
    if engine.tasks.pending: raise AssertionError('Engine worker did not settle')

class EgressTests(unittest.TestCase):
    def test_direct_tun_country_must_match_its_verified_proxy_country(self):
        with tempfile.TemporaryDirectory() as tmp:
            e=Engine(Path(tmp));e.state='checking';e.mode='tun';e.proxy_country='DE';e.probe_started=time.monotonic()
            e._probe_done(Reply('IR'),'startup-direct',True,0)
            drain(e)
            self.assertEqual(e.state,'error');self.assertIn('exit differs',e.message)

    def test_verified_tun_country_is_visible_without_storing_ip(self):
        with tempfile.TemporaryDirectory() as tmp:
            e=Engine(Path(tmp));e.state='checking';e.mode='tun';e.proxy_country='DE';e.probe_started=time.monotonic()
            e._start_bridge=MagicMock()
            e._probe_done(Reply('DE'),'startup-direct',True,0)
            self.assertEqual(e.state,'checking')
            e._bridge_ready();drain(e)
            self.assertEqual(e.state,'connected');self.assertIn('Exit: DE',e.message)
            self.assertNotIn('not-logged',(Path(tmp)/'status.json').read_text())

    def test_each_probe_clears_pooled_connections_before_switching_proxy(self):
        with tempfile.TemporaryDirectory() as tmp:
            e=Engine(Path(tmp));e.net=MagicMock()
            e._probe('startup-direct',direct=True)
            e.net.clearConnectionCache.assert_called_once()
            self.assertLess([x[0] for x in e.net.mock_calls].index('clearConnectionCache'),[x[0] for x in e.net.mock_calls].index('get'))
            e.probe_timer.stop()

class ResponsiveLifecycleTests(unittest.TestCase):
    def test_slow_socks_handshake_does_not_block_qt(self):
        from PyQt6.QtCore import QTimer
        from PyQt6.QtNetwork import QTcpServer,QHostAddress
        with tempfile.TemporaryDirectory() as tmp:
            server=QTcpServer();self.assertTrue(server.listen(QHostAddress('127.0.0.1'),0))
            peers=[]
            def accept():
                peer=server.nextPendingConnection();peers.append(peer)
                QTimer.singleShot(200,lambda:peer.write(b'\x05\x00'))
            server.newConnection.connect(accept)
            e=Engine(Path(tmp));e.state='starting';e.port=server.serverPort();e.deadline=time.monotonic()+3
            e._probe=MagicMock();ticks=[]
            timer=QTimer();timer.setInterval(10);timer.timeout.connect(lambda:ticks.append(1));timer.start()
            e._poll();self.assertEqual(e.state,'starting')
            QTest.qWait(320);timer.stop();drain(e)
            self.assertGreater(len(ticks),8)
            e._probe.assert_called_once_with('startup',direct=False)
            for peer in peers:peer.abort()
            server.close()

    def test_cancel_during_preparation_cannot_start_a_late_core(self):
        import threading
        from types import SimpleNamespace
        from unittest.mock import patch
        release=threading.Event()
        def prepare(*_):
            release.wait(3)
            return SimpleNamespace(encode=lambda:{'argv':['never-start.exe'],'env':{},'cwd':'unused'})
        with tempfile.TemporaryDirectory() as tmp,patch('tesla_vpn.engine.prepare',prepare):
            e=Engine(Path(tmp))
            try:
                e.start(None,'proxy');e.stop()
                self.assertEqual(e.state,'stopping')
                QTest.qWait(80);self.assertIsNone(e.core)
            finally:release.set();drain(e)
            self.assertEqual(e.state,'idle');self.assertIsNone(e.core)

    def test_cancel_during_proxy_activation_restores_after_activation(self):
        import threading
        release=threading.Event();order=[]
        class Proxy:
            def activate(self,*_):release.wait(3);order.append('activate')
            def restore(self):order.append('restore')
        with tempfile.TemporaryDirectory() as tmp:
            e=Engine(Path(tmp));e.state='checking';e.mode='proxy';e.port=12345;e.http_port=12346
            e.proxy=Proxy();e.pending_result='Connected'
            try:
                e._bridge_ready();QTest.qWait(40);e.stop();QTest.qWait(80)
                self.assertEqual(e.state,'stopping')
            finally:release.set();drain(e)
            self.assertEqual(order,['activate','restore']);self.assertEqual(e.state,'idle')

    def test_bridge_readiness_is_event_driven_and_required_before_green(self):
        from unittest.mock import patch
        from PyQt6.QtCore import QTimer
        args=[sys.executable,'-u','-c','import time,sys;time.sleep(.25);print(\'{"event":"http-ready"}\',flush=True);sys.stdin.read()']
        with tempfile.TemporaryDirectory() as tmp,patch('tesla_vpn.engine.command',return_value=args):
            e=Engine(Path(tmp));e.state='checking';e.mode='tun';e.port=12345;e.http_port=12346
            e.pending_result='Ready';ticks=[];timer=QTimer();timer.setInterval(10)
            timer.timeout.connect(lambda:ticks.append(1));timer.start()
            try:
                e._start_bridge();self.assertEqual(e.state,'checking')
                deadline=time.monotonic()+5
                while e.state=='checking' and time.monotonic()<deadline:QTest.qWait(10)
                self.assertEqual(e.state,'connected');self.assertGreater(len(ticks),8)
            finally:
                timer.stop();e.stop()
                deadline=time.monotonic()+5
                while e.state=='stopping' and time.monotonic()<deadline:QTest.qWait(10)
                drain(e)
            self.assertEqual(e.state,'idle')


class StaleProbeTests(unittest.TestCase):
    def test_reply_from_cancelled_session_cannot_touch_new_session(self):
        with tempfile.TemporaryDirectory() as tmp:
            e=Engine(Path(tmp));e.epoch=3;e.state='checking'
            current=object();e.reply=current;e.probe_timer.start(10000)
            old=MagicMock()
            e._probe_done(old,'startup',False,0,epoch=1)
            old.deleteLater.assert_called_once();old.readAll.assert_not_called()
            self.assertIs(e.reply,current);self.assertEqual(e.state,'checking')
            self.assertTrue(e.probe_timer.isActive());e.probe_timer.stop()
