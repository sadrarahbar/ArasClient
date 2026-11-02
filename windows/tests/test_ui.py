import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import tempfile
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from PyQt6.QtWidgets import QApplication,QPushButton
from PyQt6.QtCore import Qt
from tesla_vpn.ui import Window,QRDialog

app=QApplication.instance() or QApplication([])

class UITests(unittest.TestCase):
    def test_window_size_default_tun_and_three_import_methods(self):
        with tempfile.TemporaryDirectory() as tmp:
            w=Window(Path(tmp));w.show();app.processEvents()
            self.assertEqual((w.width(),w.height()),(451,852))
            self.assertTrue(w.tun.isChecked());self.assertFalse(w.power.isVisible())
            w.sheet.open();app.processEvents()
            buttons=w.sheet.panel.findChildren(QPushButton)
            self.assertEqual(len(buttons),3)
            self.assertTrue(all(b.text().startswith('＋') for b in buttons))
            w.sheet.hide();w.import_text('aether://?protocol=masque#test');app.processEvents()
            self.assertTrue(w.power.isVisible());self.assertEqual(w.import_button.text(),'Replace configuration')
            self.assertEqual((w.power.width(),w.power.height()),(171,171))
            from PyQt6.QtCore import QPoint
            for widget in [w.power,w.test_button,w.import_button,w.mode_box,w.message]:
                point=widget.mapTo(w,QPoint(0,0))
                self.assertGreaterEqual(point.x(),0);self.assertGreaterEqual(point.y(),0)
                self.assertLessEqual(point.x()+widget.width(),451)
                self.assertLessEqual(point.y()+widget.height(),852)
            power_top=w.power.mapTo(w,QPoint(0,0)).y()
            hint_bottom=w.hint.mapTo(w,QPoint(0,0)).y()+w.hint.height()
            self.assertEqual(power_top,352)
            self.assertEqual(hint_bottom,191)
            self.assertEqual(w.mode_box.y(),223)
            self.assertEqual((w.glow.width(),w.glow.height()),(446,446))
            self.assertFalse(w.glow.pixmap().isNull())
            self.assertFalse(w.power.symbol.isNull())
            self.assertEqual(w.title.font().family(),"Geologica")
            self.assertGreaterEqual(w.hint.width(),w.hint.fontMetrics().horizontalAdvance(w.hint.text()))
            import_bottom=w.import_button.mapTo(w,QPoint(0,0)).y()+w.import_button.height()
            self.assertEqual(w.height()-import_bottom,36)
            w.sheet.open();w.sheet.animation.setCurrentTime(200);app.processEvents()
            for button in w.sheet.panel.findChildren(QPushButton):
                point=button.mapTo(w,QPoint(0,0))
                self.assertGreaterEqual(point.y(),0);self.assertLessEqual(point.y()+button.height(),852)
            w.sheet.hide()
            from PyQt6.QtTest import QTest
            self.assertEqual(w.proxy.height(),28)
            QTest.mouseClick(w.proxy,Qt.MouseButton.LeftButton,pos=QPoint(w.proxy.width()-2,w.proxy.height()//2))
            self.assertTrue(w.proxy.isChecked());self.assertFalse(w.tun.isChecked())
            w.engine._set('connected','Test connection');app.processEvents()
            self.assertEqual(w.power.color,'#35D88A');self.assertFalse(w.import_button.isEnabled())
            w.engine._set('idle','Disconnected')
            self.assertEqual(w.status.text(),'Disconnected')
            self.assertEqual(w.message.text(),'')
            self.assertFalse(w.message.isVisible())
            w.close()
            import time
            from PyQt6.QtTest import QTest
            deadline=time.monotonic()+5
            while w.engine.tasks.pending and time.monotonic()<deadline:QTest.qWait(10)
            self.assertFalse(w.engine.tasks.pending)

    def test_qr_import_decodes_real_image(self):
        from io import BytesIO
        import qrcode
        text='aether://?protocol=masque&transport=h2#QR'
        data=BytesIO();qrcode.make(text).save(data,format='PNG')
        found=[];d=QRDialog(None,found.append)
        self.assertTrue(d.decode(data.getvalue()));self.assertEqual(found,[text]);d.close()

class AnimationTests(unittest.TestCase):
    def test_status_updates_do_not_restart_continuous_animation(self):
        from tesla_vpn.ui import PowerButton
        from PyQt6.QtTest import QTest,QSignalSpy
        from PyQt6.QtCore import QAbstractAnimation
        button=PowerButton();button.status(False,True)
        frames=QSignalSpy(button.animation.valueChanged)
        try:
            for _ in range(8):
                QTest.qWait(25);button.status(False,True)
            self.assertGreaterEqual(button.animation.currentTime(),120)
            self.assertGreaterEqual(len(frames),5)
        finally:button.status(False,False)
        self.assertEqual(button.animation.state(),QAbstractAnimation.State.Stopped)
