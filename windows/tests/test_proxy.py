from pathlib import Path
import sys,tempfile,unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from tesla_vpn.system_proxy import SystemProxy,WinInet

class FakeAPI:
    def __init__(self):
        self.value={'flags':13,'server':'old.example:8080','bypass':'old-local','pac':'https://old.example/proxy.pac'}
        self.fail_once=False
    def read(self):return dict(self.value)
    def write(self,value):
        self.value=dict(value)
        if self.fail_once:self.fail_once=False;raise OSError('partial write')

class ProxyTests(unittest.TestCase):
    def test_restore_all_old_proxy_and_pac_flags(self):
        with tempfile.TemporaryDirectory() as d:
            api=FakeAPI();old=api.read();p=SystemProxy(Path(d),api)
            p.activate(1080,8080);self.assertEqual(api.value['flags'],3);self.assertEqual(api.value['pac'],'')
            self.assertIn('https=127.0.0.1:8080',api.value['server'])
            p.restore();self.assertEqual(api.value,old);self.assertFalse(p.backup.exists())
    def test_partial_failure_restores_previous_settings(self):
        with tempfile.TemporaryDirectory() as d:
            api=FakeAPI();old=api.read();api.fail_once=True;p=SystemProxy(Path(d),api)
            with self.assertRaises(OSError):p.activate(1080,8080)
            self.assertEqual(api.value,old);self.assertFalse(p.backup.exists())
    def test_crash_recovery_preserves_independent_user_changes(self):
        with tempfile.TemporaryDirectory() as d:
            api=FakeAPI();p=SystemProxy(Path(d),api);p.activate(1080,8080)
            api.value['bypass']='my-new-exceptions'
            SystemProxy(Path(d),api).restore()
            self.assertEqual(api.value['bypass'],'my-new-exceptions');self.assertEqual(api.value['flags'],13)

@unittest.skipUnless(sys.platform=='win32','Native WinINET integration requires Windows')
class NativeProxyTests(unittest.TestCase):
    def test_real_wininet_read_and_identical_write(self):
        api=WinInet();original=api.read()
        try:api.write(original);self.assertEqual(api.read(),original)
        finally:api.write(original)
