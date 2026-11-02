import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from pathlib import Path
import sys, tempfile, time, unittest
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from PyQt6.QtWidgets import QApplication
from PyQt6.QtNetwork import QNetworkReply
from PyQt6.QtTest import QTest
from tesla_vpn.ui import Window
app = QApplication.instance() or QApplication([])

class Reply:
    def __init__(self, country='DE', ok=True): self.country=country; self.ok=ok
    def attribute(self, key): return 200 if self.ok else None
    def error(self): return QNetworkReply.NetworkError.NoError if self.ok else QNetworkReply.NetworkError.ConnectionRefusedError
    def readAll(self): return (('loc='+self.country+'\n') if self.country else '').encode()
    def deleteLater(self): pass

def finish(w):
    w.engine._set('idle', 'Disconnected'); w.close()
    deadline=time.monotonic()+5
    while w.engine.tasks.pending and time.monotonic()<deadline: QTest.qWait(10)
    assert not w.engine.tasks.pending

class ProbeSessionTests(unittest.TestCase):
    def test_actual_manual_probe_result_preserves_clock_and_expires_only_detail(self):
        for ok in (True, False):
            with self.subTest(ok=ok), tempfile.TemporaryDirectory() as d:
                w=Window(Path(d)); w.show(); w.import_text('aether://?protocol=wg#test')
                e=w.engine
                try:
                    with patch('tesla_vpn.engine.time.monotonic', return_value=100): e._set('connected', 'Initial result')
                    e.exit_country='DE'; e.probe_started=164.5; e.testing=True
                    with patch('tesla_vpn.engine.time.monotonic', return_value=165):
                        e._probe_done(Reply(ok=ok), 'manual', False, 0 if ok else 1)
                        self.assertEqual(e.session_seconds, 65)
                        self.assertEqual(w.session_time.text(), '00:01:05')
                        self.assertTrue(w.message.isVisible())
                        self.assertEqual(e.result_timer.interval(), 5000)
                        e.result_timer.start(25); QTest.qWait(80)
                        self.assertFalse(w.message.isVisible())
                        self.assertEqual(e.message, '')
                        self.assertEqual(e.state, 'connected')
                        self.assertEqual(e.connected_at, 100)
                        self.assertEqual(e.exit_country, 'DE')
                        self.assertTrue(w.session_timer.isActive())
                    with patch('tesla_vpn.engine.time.monotonic', return_value=166):
                        w.update_session(); self.assertEqual(w.session_time.text(), '00:01:06')
                finally: finish(w)

    def test_fallback_without_country_keeps_last_measured_exit(self):
        with tempfile.TemporaryDirectory() as d:
            w=Window(Path(d)); e=w.engine
            try:
                e._set('connected', 'Initial'); e.exit_country='DE'; e.probe_started=time.monotonic()
                e._probe_done(Reply(country=None), 'manual', False, 1)
                self.assertEqual(e.exit_country, 'DE')
                self.assertEqual(e.state, 'connected')
            finally: finish(w)

    def test_new_check_cancels_previous_result_expiry_and_disconnect_cancels_timer(self):
        with tempfile.TemporaryDirectory() as d:
            w=Window(Path(d)); e=w.engine
            try:
                e._set('connected', 'Initial'); e.result_timer.start(25)
                with patch.object(e, '_probe') as probe:
                    e.test(); probe.assert_called_once_with('manual', direct=True)
                self.assertFalse(e.result_timer.isActive())
                QTest.qWait(80); self.assertEqual(e.message, 'Testing…')
                e.probe_started=time.monotonic(); e._probe_done(Reply(), 'manual', False, 0)
                self.assertTrue(e.result_timer.isActive())
                e.stop()
                self.assertFalse(e.result_timer.isActive())
            finally: finish(w)
