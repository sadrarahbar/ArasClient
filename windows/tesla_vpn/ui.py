"""Tesla Vpn desktop UI matching Figma frame 12:3 at its native 451 × 852 size."""
from io import BytesIO
import re
from pathlib import Path
import shutil
import xml.etree.ElementTree as ET
from PyQt6.QtCore import Qt, QRectF, QTimer, QProcess, QPoint, QPropertyAnimation, QEasingCurve
from PyQt6.QtGui import QColor, QPainter, QPainterPath, QPen, QPixmap, QIcon, QTransform, QFont, QFontDatabase, QImageReader
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QAbstractButton, QFrame, QRadioButton, QButtonGroup, QFileDialog, QMessageBox,
    QDialog, QScrollArea, QComboBox)
from .engine import Engine
from .profiles import ProfileStore, ImportError, MAX_IMPORT
from .runtime import resources

BG = "#0F1626"
RED, GREEN, AMBER = "#E74E62", "#35D88A", "#F4BE63"


def svg_paths(filename):
    root = ET.parse(filename).getroot()
    result = []
    for item in root.findall("{http://www.w3.org/2000/svg}path"):
        path = QPainterPath(); tokens = iter(re.findall(r"[MLHVZmlhvz]|[-+]?(?:\d*\.\d+|\d+\.?\d*)(?:[eE][-+]?\d+)?", item.attrib["d"]))
        x = y = 0
        for token in tokens:
            if token == "M": x, y = float(next(tokens)), float(next(tokens)); path.moveTo(x, y)
            elif token == "L": x, y = float(next(tokens)), float(next(tokens)); path.lineTo(x, y)
            elif token == "H": x = float(next(tokens)); path.lineTo(x, y)
            elif token == "V": y = float(next(tokens)); path.lineTo(x, y)
            elif token in ("Z", "z"): path.closeSubpath()
            else: raise ValueError("Unsupported logo path")
        result.append((path, QColor(item.attrib.get("fill", "#121C31"))))
    return result


def app_icon():
    pixmap = QPixmap(300, 300); pixmap.fill(Qt.GlobalColor.transparent)
    p = QPainter(pixmap); p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setPen(Qt.PenStyle.NoPen); p.setBrush(QColor("white")); p.drawRoundedRect(QRectF(0, 0, 300, 300), 50, 50)
    for path, color in svg_paths(resources() / "assets/app-logo.svg"): p.fillPath(path, color)
    p.end(); return QIcon(pixmap)


def design_font(size, weight=QFont.Weight.Normal):
    font = QFont("Geologica")
    font.setPixelSize(size)
    font.setWeight(weight)
    for tag, value in (("wght", weight.value), ("CRSV", 0), ("SHRP", 0), ("slnt", 0)):
        font.setVariableAxis(QFont.Tag.fromString(tag), value)
    return font


class ConnectionGlow(QLabel):
    """Tint the design's original glow without changing its opacity or shape."""
    def __init__(self, parent):
        super().__init__(parent)
        self.source = (resources() / "assets/figma/connection-glow.svg").read_bytes()
        self.original = QPixmap()
        self.original.loadFromData(self.source, "SVG")
        self.variants = {RED: self.original}
        self.set_color(RED)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

    def set_color(self, color):
        if color not in self.variants:
            # Change only the center stop; keep the dark outer stop, falloff,
            # transparency and dimensions exactly as exported from Figma.
            tinted = QPixmap()
            tinted.loadFromData(self.source.replace(RED.encode(), color.encode()), "SVG")
            self.variants[color] = tinted
        self.setPixmap(self.variants[color])


class PowerButton(QAbstractButton):
    def __init__(self):
        super().__init__(); self.setFixedSize(171, 171)
        self.setCursor(Qt.CursorShape.PointingHandCursor); self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        # Keep the original Figma SVG unmodified, including its intrinsic dimensions.
        reader = QImageReader(str(resources() / "assets/figma/tesla-symbol.svg"))
        from PyQt6.QtCore import QSize
        reader.setScaledSize(QSize(445, 295))
        self.symbol = QPixmap.fromImage(reader.read())
        self.color = RED; self.connecting = False; self.angle = 0
        self.timer = QTimer(self); self.timer.setInterval(60); self.timer.timeout.connect(self.spin)
        self.setAccessibleName("Connect")

    def spin(self): self.angle = (self.angle + 8) % 360; self.update()

    def status(self, connected, connecting):
        self.color = GREEN if connected else AMBER if connecting else RED
        self.connecting = connecting
        if connecting: self.timer.start()
        else: self.timer.stop()
        self.setAccessibleName("Disconnect or cancel" if connected or connecting else "Connect")
        self.update()

    def paintEvent(self, event):
        p = QPainter(self); p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(Qt.PenStyle.NoPen); p.setBrush(QColor(self.color))
        p.drawEllipse(QRectF(0, 0, 171, 171))
        p.setPen(QPen(QColor(BG), 1))
        p.drawEllipse(QRectF(6, 6.5, 159, 159))
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        p.drawPixmap(QRectF(30.2593, 63.0037, 111.0991, 73.6882), self.symbol, QRectF(self.symbol.rect()))
        if self.connecting or (self.hasFocus() and self.window().testAttribute(Qt.WidgetAttribute.WA_KeyboardFocusChange)):
            p.setBrush(Qt.BrushStyle.NoBrush); p.setPen(QPen(QColor(BG), 2))
            p.drawArc(QRectF(10, 10, 151, 151), self.angle * 16, 100 * 16) if self.connecting else p.drawEllipse(QRectF(10, 10, 151, 151))
        p.end()


class ModeRadioButton(QRadioButton):
    """Native radio keyboard/selection behavior with the exact Figma indicator."""
    def __init__(self, text):
        super().__init__(text)
        self.setFixedSize(188, 28)
        self.setFont(design_font(22, QFont.Weight.Light))
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def hitButton(self, position):
        return self.rect().contains(position)

    def paintEvent(self, event):
        p = QPainter(self); p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(QPen(QColor("white"), 1.4 if self.isChecked() else 1))
        p.setBrush(Qt.BrushStyle.NoBrush); p.drawEllipse(QRectF(.7, .7, 26.6, 26.6))
        if self.isChecked():
            p.setPen(Qt.PenStyle.NoPen); p.setBrush(QColor("white")); p.drawEllipse(QRectF(7, 7, 14, 14))
        p.setPen(QColor("#A6A6A6")); p.setFont(self.font())
        p.drawText(QRectF(37 if self.isChecked() else 38, 0, 151, 28), Qt.AlignmentFlag.AlignVCenter, self.text())
        if self.hasFocus() and self.window().testAttribute(Qt.WidgetAttribute.WA_KeyboardFocusChange):
            p.setPen(QPen(QColor("#98ABD5"), 1, Qt.PenStyle.DotLine))
            p.setBrush(Qt.BrushStyle.NoBrush); p.drawRoundedRect(QRectF(.5, .5, 187, 27), 5, 5)
        p.end()


class ImportSheet(QWidget):
    def __init__(self, window, callback):
        super().__init__(window); self.setObjectName("sheetOverlay")
        self.setStyleSheet("QWidget#sheetOverlay {background: rgba(0,0,0,140);}")
        self.panel = QFrame(self); self.panel.setObjectName("importPanel")
        self.panel.setStyleSheet("QFrame#importPanel {background:#141F33;border-top-left-radius:18px;border-top-right-radius:18px;}")
        layout = QVBoxLayout(self.panel); layout.setContentsMargins(20, 6, 20, 12); layout.setSpacing(2)
        handle = QLabel("━━━━"); handle.setAlignment(Qt.AlignmentFlag.AlignCenter); handle.setStyleSheet("color:#63708A;font-size:13px;"); handle.setFixedHeight(12)
        layout.addWidget(handle)
        title = QLabel("Import configuration"); title.setStyleSheet("font-size:19px;font-weight:600;color:white;"); layout.addWidget(title)
        for label, action in [("Import from QR code", "qr"), ("Import from clipboard", "clipboard"), ("Import from a local file", "file")]:
            row = QPushButton("＋   " + label); row.setMinimumHeight(40)
            row.setCursor(Qt.CursorShape.PointingHandCursor)
            row.setStyleSheet("QPushButton {text-align:left;border:0;border-radius:12px;padding:6px;color:white;background:transparent;font-size:16px;} QPushButton:hover,QPushButton:focus {background:#24324C;}")
            row.clicked.connect(lambda checked=False, a=action: (self.hide(), callback(a)))
            layout.addWidget(row)
        self.animation = QPropertyAnimation(self.panel, b"pos", self); self.animation.setDuration(200)
        self.animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.hide()

    def open(self):
        self.setGeometry(self.parentWidget().rect()); height = min(220, self.height() - 8)
        self.panel.resize(self.width(), height); self.show(); self.raise_()
        self.animation.setStartValue(QPoint(0, self.height())); self.animation.setEndValue(QPoint(0, self.height() - height))
        self.animation.start(); self.panel.findChildren(QPushButton)[0].setFocus()

    def mousePressEvent(self, event):
        if event.position().y() < self.panel.y(): self.hide()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape: self.hide()
        else: super().keyPressEvent(event)


class QRDialog(QDialog):
    def __init__(self, parent, callback):
        super().__init__(parent); self.callback = callback; self.camera = None; self.buffer = b""
        self.setWindowTitle("Import from QR code"); self.resize(520, 500)
        self.setStyleSheet(f"QDialog {{background:{BG};color:white;}} QLabel {{color:white;}} QPushButton {{padding:12px;}}")
        layout = QVBoxLayout(self)
        self.preview = QLabel("Choose a QR image to import."); self.preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview.setMinimumHeight(280); layout.addWidget(self.preview)
        image = QPushButton("Open QR image"); image.clicked.connect(self.image); layout.addWidget(image)
        close = QPushButton("Cancel"); close.clicked.connect(self.reject); layout.addWidget(close)

    def decode(self, data):
        from PIL import Image
        import zxingcpp
        with Image.open(BytesIO(data)) as image:
            if image.width * image.height > 32_000_000: raise ValueError("QR image is too large.")
            results = zxingcpp.read_barcodes(image, formats=zxingcpp.BarcodeFormat.QRCode)
        for result in results:
            if result.valid:
                self.callback(result.text); self.accept(); return True
        return False

    def image(self):
        filename, _ = QFileDialog.getOpenFileName(self, "Open QR image", "", "Images (*.png *.jpg *.jpeg *.webp *.bmp)")
        if not filename: return
        try:
            path = Path(filename)
            if path.stat().st_size > MAX_IMPORT: raise ValueError("QR image exceeds 8 MB.")
            if not self.decode(path.read_bytes()): QMessageBox.information(self, "QR code", "No QR code was found in the image.")
        except Exception: QMessageBox.warning(self, "QR code", "Could not read this QR image.")



class Window(QMainWindow):
    def __init__(self, root):
        super().__init__(); self.setWindowTitle("Tesla Vpn"); self.setWindowIcon(app_icon())
        self.setFixedSize(451, 852)
        QFontDatabase.addApplicationFont(str(resources() / "assets/figma/Geologica.ttf"))
        self.setFont(design_font(20))
        self.root = root; self.store = ProfileStore(root); self.engine = Engine(root)
        self.profile = None; self.initial_error = ""
        try: self.profile = self.store.load()
        except ImportError as error: self.initial_error = str(error)
        try: self.engine.proxy.restore()
        except Exception: self.initial_error = "Proxy recovery failed. Check desktop proxy settings before connecting."
        self.setStyleSheet(f"QMainWindow,QWidget#content {{background:{BG};}} QLabel {{color:#A5A5A5;background:transparent;}} QToolTip {{color:white;background:#24324C;}}")
        content = QWidget(); content.setObjectName("content"); self.setCentralWidget(content)
        # This is a fixed-size Figma canvas. Native widgets retain their interactions
        # and keyboard focus while their design slots match frame 12:3 exactly.
        self.glow = ConnectionGlow(content)
        self.glow.setGeometry(2, 215, 446, 446)
        self.title = QLabel("Tesla Vpn", content)
        self.title.setGeometry(76, 111, 298, 51); self.title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.title.setFont(design_font(40, QFont.Weight.Bold)); self.title.setStyleSheet("color:white;")
        self.hint = QLabel(content); self.hint.setGeometry(65, 166, 321, 25)
        self.hint.setFont(design_font(20)); self.hint.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.mode_box = QFrame(content); self.mode_box.setGeometry(131, 223, 188, 68)
        self.tun = ModeRadioButton("System tunnel"); self.tun.setParent(self.mode_box); self.tun.move(0, 0); self.tun.setChecked(True)
        self.tun.setToolTip("Routes system traffic; requires administrator permission.")
        self.proxy = ModeRadioButton("System proxy"); self.proxy.setParent(self.mode_box); self.proxy.move(0, 40)
        self.proxy.setToolTip("No administrator access; applications must honor system proxy settings.")
        group = QButtonGroup(self); group.addButton(self.tun); group.addButton(self.proxy)
        self.power = PowerButton(); self.power.setParent(content); self.power.move(140, 352)
        self.power.clicked.connect(self.toggle)
        self.status = QLabel(content); self.status.setGeometry(95, 540, 261, 25)
        self.status.setFont(design_font(20, QFont.Weight.Medium)); self.status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.test_button = QPushButton("Check connectivity", content); self.test_button.setGeometry(128, 581, 195, 37)
        self.test_button.setFont(design_font(18, QFont.Weight.Light)); self.test_button.clicked.connect(self.engine.test)
        self.test_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.test_button.setStyleSheet("QPushButton {color:#98ABD5;background:transparent;border:1px solid #98ABD5;border-radius:18px;padding:0;} QPushButton:hover {background:#19253A;} QPushButton:focus {border:2px solid #98ABD5;}")
        self.message = QLabel(content); self.message.setGeometry(45, 635, 361, 100)
        self.message.setFont(design_font(14)); self.message.setAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop)
        self.message.setWordWrap(True)
        self.import_button = QPushButton(content); self.import_button.setGeometry(110, 779, 238, 37)
        self.import_button.setFont(design_font(20, QFont.Weight.Light)); self.import_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.import_button.setStyleSheet("QPushButton {color:#98ABD5;background:#19253A;border:0;border-radius:18px;padding:0;} QPushButton:hover {background:#24324C;} QPushButton:focus {border:1px solid #98ABD5;} QPushButton:disabled {color:#556278;}")
        self.sheet = ImportSheet(self, self.import_action); self.import_button.clicked.connect(self.sheet.open)
        self.engine.changed.connect(self.render)
        self.engine.notice.connect(lambda text: QMessageBox.warning(self, "Tesla Vpn", text))
        self.render()
        if self.initial_error: QTimer.singleShot(200, lambda: QMessageBox.warning(self, "Tesla Vpn", self.initial_error))

    def render(self):
        engine = self.engine; has = self.profile is not None
        self.hint.setText("Your connection, one tap away" if has else "Import a configuration to start")
        self.import_button.show()
        self.power.setVisible(has); self.glow.setVisible(has)
        self.status.setVisible(has); self.test_button.setVisible(has); self.mode_box.setVisible(has)
        self.power.status(engine.state == "connected", engine.busy)
        self.glow.set_color(self.power.color)
        self.power.setEnabled(engine.state != "stopping")
        text, color = {"idle": ("Disconnected", RED), "connected": ("Connected", GREEN), "error": ("Connection failed", RED),
                       "starting": ("Connecting…", AMBER), "checking": ("Connecting…", AMBER), "stopping": ("Disconnecting…", AMBER)}[engine.state]
        self.status.setText(text + (" · TUN" if engine.mode == "tun" else " · Proxy") if engine.state == "connected" else text); self.status.setStyleSheet(f"color:{color};")
        detail = engine.message if has else "Only one configuration is kept on this device."
        if detail.strip().casefold() == text.casefold() or detail == "Configuration imported. Ready to connect.": detail = ""
        self.message.setText(detail)
        self.message.setVisible(bool(detail))
        self.test_button.setText("Testing…" if engine.testing else "Check connectivity")
        self.test_button.setEnabled(engine.state == "connected" and not engine.testing)
        self.mode_box.setEnabled(engine.state in ("idle", "error"))
        self.import_button.setText("Replace configuration" if has else "Import configuration")
        self.import_button.setEnabled(engine.state in ("idle", "error"))

    def toggle(self):
        from .win32 import is_admin, elevate
        if self.engine.state in ("idle", "error") and self.profile and self.tun.isChecked() and not is_admin():
            try:
                elevate(self.root)
                QApplication.instance().quit()
            except OSError as error:
                QMessageBox.warning(self, "Tesla Vpn", str(error))
            return
        if self.engine.state in ("connected", "starting", "checking"): self.engine.stop()
        elif self.profile: self.engine.start(self.profile, "tun" if self.tun.isChecked() else "proxy")

    def import_action(self, action):
        if action == "clipboard": self.import_text(QApplication.clipboard().text())
        elif action == "file":
            filename, _ = QFileDialog.getOpenFileName(self, "Import configuration", "", "VPN configurations (*.txt *.json *.conf);;All files (*)")
            if filename:
                try:
                    path = Path(filename)
                    if path.suffix.lower() == ".arasc":
                        raise ImportError("For Android .arasc profiles, use Export to Nekoray on Android and import that link here.")
                    if path.stat().st_size > MAX_IMPORT: raise ImportError("Configuration exceeds 8 MB.")
                    self.import_text(path.read_text(encoding="utf-8-sig"))
                except (OSError, UnicodeError, ImportError) as e:
                    QMessageBox.warning(self, "Import", str(e) if isinstance(e, ImportError) else "Could not read the selected file.")
        else: QRDialog(self, self.import_text).exec()

    def import_text(self, text):
        try:
            self.profile = self.store.import_text(text)
            self.engine.message = "Configuration imported. Ready to connect."; self.render()
        except (ImportError, OSError) as error:
            QMessageBox.warning(self, "Import", str(error) if isinstance(error, ImportError) else "Could not save the configuration.")

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, "sheet") and self.sheet.isVisible(): self.sheet.open()

    def closeEvent(self, event):
        if self.engine.state not in ("idle", "error"):
            self.engine.stop()
            if self.engine.core is not None and not self.engine.core.waitForFinished(12000):
                event.ignore(); QMessageBox.information(self, "Tesla Vpn", "Waiting for VPN routes to be restored. Please close again in a moment."); return
        event.accept()
