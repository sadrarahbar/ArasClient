"""Serialize blocking work off the GUI thread; worker threads never touch Qt objects."""
from concurrent.futures import ThreadPoolExecutor
import queue
import weakref
from PyQt6.QtCore import QObject, QTimer


class Tasks(QObject):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.pending = 0; self.results = queue.Queue()
        self.pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix='TeslaSettings')
        self.timer = QTimer(self); self.timer.setInterval(8); self.timer.timeout.connect(self._deliver)
        weakref.finalize(self, self.pool.shutdown, wait=False)

    def submit(self, operation, callback):
        self.pending += 1
        self.timer.start()
        output = self.results
        future = self.pool.submit(operation)
        def done(result):
            try: value, error = result.result(), None
            except Exception as exc: value, error = None, exc
            output.put((callback, value, error))
        future.add_done_callback(done)

    def _deliver(self):
        while True:
            try: callback, value, error = self.results.get_nowait()
            except queue.Empty: break
            self.pending -= 1
            callback(value, error)
        if not self.pending: self.timer.stop()
