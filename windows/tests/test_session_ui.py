import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from pathlib import Path
import sys, tempfile, unittest
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt
from PyQt6.QtTest import QTest
from tesla_vpn.ui import Window
app = QApplication.instance() or QApplication([])

class SessionPresentationTests(unittest.TestCase):
    def test_session_clock_country_buttons_and_disabled_modes_follow_connection(self):
        with tempfile.TemporaryDirectory() as d:
            w = Window(Path(d)); w.show()
            w.import_text('aether://?protocol=wg#session')
            app.processEvents()
            self.assertTrue(w.import_button.isVisible())
            self.assertFalse(w.test_button.isVisible())
            self.assertFalse(w.session_time.isVisible())
            self.assertTrue(w.tun.isEnabled())
            with patch('tesla_vpn.engine.time.monotonic', return_value=100):
                w.engine._set('connected', 'Connection verified')
            w.engine.exit_country = 'DE'
            with patch('tesla_vpn.engine.time.monotonic', return_value=165):
                w.render()
                self.assertEqual(w.session_time.text(), '00:01:05')
                w.engine._set('connected', 'Retested')
                self.assertEqual(w.engine.connected_at, 100)
            self.assertEqual(w.country_name.text(), 'Germany')
            self.assertFalse(w.country_flag.pixmap().isNull())
            self.assertTrue(w.test_button.isVisible())
            self.assertFalse(w.import_button.isVisible())
            self.assertFalse(w.tun.isEnabled()); self.assertFalse(w.proxy.isEnabled())
            QTest.mouseClick(w.proxy, Qt.MouseButton.LeftButton)
            self.assertTrue(w.tun.isChecked())
            w.engine.exit_country = None; w.render()
            self.assertEqual(w.country_name.text(), 'Unknown country')
            self.assertFalse(w.country_flag.isVisible())
            w.engine._set('stopping', 'Stopping')
            self.assertFalse(w.test_button.isVisible())
            self.assertFalse(w.session_time.isVisible())
            self.assertFalse(w.proxy.isEnabled())
            w.engine._set('idle', 'Disconnected')
            self.assertEqual(w.engine.session_seconds, 0)
            self.assertTrue(w.import_button.isVisible()); self.assertTrue(w.proxy.isEnabled())
            self.assertFalse(w.session_timer.isActive())
            with patch('tesla_vpn.engine.time.monotonic', return_value=300):
                w.engine._set('connected', 'New session')
                self.assertEqual(w.engine.session_seconds, 0)
            w.engine._set('idle', 'Disconnected'); w.close()
            if hasattr(w.engine, 'tasks'):
                import time
                deadline = time.monotonic() + 5
                while w.engine.tasks.pending and time.monotonic() < deadline: QTest.qWait(10)
                self.assertEqual(w.engine.tasks.pending, 0)
