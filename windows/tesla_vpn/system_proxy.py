"""Current-user WinINET proxy settings with exact snapshot and crash recovery."""
import ctypes
from ctypes import wintypes
import json
from pathlib import Path
from .profiles import private_write


class WinInet:
    """Use connection options, including the real WPAD flag (not a guessed registry key)."""
    def __init__(self):
        self.api = ctypes.WinDLL('wininet', use_last_error=True)
        class Value(ctypes.Union):
            _fields_ = [('number', wintypes.DWORD), ('text', ctypes.c_void_p), ('time', wintypes.FILETIME)]
        class Option(ctypes.Structure):
            _fields_ = [('option', wintypes.DWORD), ('value', Value)]
        class Options(ctypes.Structure):
            _fields_ = [('size', wintypes.DWORD), ('connection', wintypes.LPWSTR),
                ('count', wintypes.DWORD), ('error', wintypes.DWORD), ('options', ctypes.POINTER(Option))]
        self.Option, self.Options = Option, Options
        self.api.InternetQueryOptionW.argtypes = [wintypes.HANDLE, wintypes.DWORD, ctypes.c_void_p, ctypes.POINTER(wintypes.DWORD)]
        self.api.InternetSetOptionW.argtypes = [wintypes.HANDLE, wintypes.DWORD, ctypes.c_void_p, wintypes.DWORD]
        self.kernel = ctypes.WinDLL('kernel32'); self.kernel.GlobalFree.argtypes = [ctypes.c_void_p]
        self.kernel.GlobalFree.restype = ctypes.c_void_p

    def _options(self):
        items = (self.Option * 4)()
        for item, number in zip(items, [1,2,3,4]): item.option = number
        data = self.Options(ctypes.sizeof(self.Options), None, 4, 0, items)
        return items, data

    def read(self):
        items, data = self._options(); length = wintypes.DWORD(ctypes.sizeof(data))
        if not self.api.InternetQueryOptionW(None, 75, ctypes.byref(data), ctypes.byref(length)):
            raise ctypes.WinError(ctypes.get_last_error())
        result = {'flags': int(items[0].value.number)}
        for key, item in zip(['server','bypass','pac'], items[1:]):
            pointer = item.value.text
            try: result[key] = ctypes.wstring_at(pointer) if pointer else ''
            finally:
                if pointer: self.kernel.GlobalFree(pointer)
        return result

    def write(self, settings):
        items, data = self._options(); buffers = []
        items[0].value.number = settings['flags']
        for key, item in zip(['server','bypass','pac'], items[1:]):
            buf = ctypes.create_unicode_buffer(settings[key]); buffers.append(buf)
            item.value.text = ctypes.cast(buf, ctypes.c_void_p).value
        if not self.api.InternetSetOptionW(None, 75, ctypes.byref(data), ctypes.sizeof(data)):
            raise ctypes.WinError(ctypes.get_last_error())
        for option in [39,37]:  # SETTINGS_CHANGED, REFRESH
            if not self.api.InternetSetOptionW(None, option, None, 0):
                raise ctypes.WinError(ctypes.get_last_error())


class SystemProxy:
    def __init__(self, root: Path, api=None):
        self.backup = root / 'proxy-recovery.json'; self.api = api

    def _api(self):
        if self.api is None: self.api = WinInet()
        return self.api

    def activate(self, socks_port, http_port):
        if self.backup.exists(): self.restore()
        old = self._api().read()
        new = {'flags': 3, 'server': f'http=127.0.0.1:{http_port};https=127.0.0.1:{http_port};socks=127.0.0.1:{socks_port}',
               'bypass': 'localhost;127.*;[::1];<local>', 'pac': ''}
        private_write(self.backup, json.dumps({'version': 1, 'old': old, 'new': new}).encode())
        try: self._api().write(new)
        except Exception:
            self.restore(); raise

    def restore(self):
        try: data = json.loads(self.backup.read_text(encoding='utf-8'))
        except FileNotFoundError: return
        if data.get('version') != 1: raise ValueError('Unsupported proxy recovery snapshot.')
        current = self._api().read()
        # Do not overwrite settings changed independently while Tesla was active.
        restored = {k: data['old'][k] if current[k] == data['new'][k] else current[k] for k in current}
        self._api().write(restored)
        self.backup.unlink(missing_ok=True)
