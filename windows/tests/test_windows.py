from pathlib import Path
import subprocess,sys,tempfile,time,unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from tesla_vpn.tun import tun_config

class ConfigTests(unittest.TestCase):
    def test_tun_uses_dual_stack_dns_over_proxy_and_exact_core_bypasses(self):
        c=tun_config(12345,Path('/bundled/cores'))
        t=c['inbounds'][0]
        self.assertTrue(t['auto_route']);self.assertTrue(t['strict_route']);self.assertEqual(len(t['address']),2)
        self.assertEqual(c['dns']['servers'][0]['detour'],'proxy')
        self.assertEqual(c['dns']['servers'][0]['type'],'https')
        rules=c['route']['rules'];self.assertEqual(rules[1],{'port':53,'action':'hijack-dns'})
        self.assertTrue(all(Path(p).name in ['aether.exe','psiphon-tunnel-core.exe','lyrebird.exe','xray.exe'] for p in rules[0]['process_path']))
        self.assertTrue(c['route']['auto_detect_interface'])
    def test_state_is_per_user_localappdata(self):
        from unittest.mock import patch
        from tesla_vpn.runtime import state_root
        with patch.dict('os.environ',{'LOCALAPPDATA':'/user/local'}):
            self.assertEqual(state_root(),Path('/user/local/TeslaVpn'))

@unittest.skipUnless(sys.platform=='win32','Windows Job Object integration requires Windows')
class JobTests(unittest.TestCase):
    def test_kill_on_owner_close_contains_process(self):
        from tesla_vpn.win32 import Job
        job=Job();child=None
        try:
            child=job.spawn([sys.executable,'-c','import time;time.sleep(60)'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
            self.assertIsNone(child.poll());job.close()
            self.assertIsNotNone(child.wait(timeout=10))
        finally:
            job.close()
            if child and child.poll() is None:child.kill();child.wait()
    def test_private_directory_blocks_inherited_public_access(self):
        from tesla_vpn.win32 import private_directory
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)/'private';private_directory(root)
            result=subprocess.check_output(['icacls',str(root)],text=True)
            self.assertNotIn('(I)',result)

    def test_runtime_accounts_inherit_private_user_acl(self):
        from tesla_vpn.win32 import private_directory
        from tesla_vpn.runtime import prepare
        from tesla_vpn.profiles import parse_import, private_write
        with tempfile.TemporaryDirectory() as d:
            root = Path(d) / 'state'; private_directory(root)
            cores = Path(d) / 'cores'; cores.mkdir(); (cores / 'xray.exe').touch()
            profile = parse_import('vless://id@example.com:443#test')
            plan = prepare(profile, 12345, root, cores)
            acl = subprocess.check_output(['icacls', plan.cwd], text=True)
            self.assertIn('(I)', acl)
            nested = root / 'nested' / 'private.json'
            private_write(nested, b'private')
            self.assertIn('(I)', subprocess.check_output(['icacls', str(nested.parent)], text=True))

    def test_migration_restores_inheritance_without_changing_identity(self):
        from unittest.mock import patch
        from tesla_vpn.win32 import private_directory, repair_account_permissions
        with tempfile.TemporaryDirectory() as d:
            root = Path(d) / 'state'; private_directory(root)
            account = root / 'accounts' / 'old'; account.mkdir(parents=True, mode=0o700)
            identity = account / 'aether-wg.toml'; identity.write_bytes(b'preserve-key')
            self.assertNotIn('(I)', subprocess.check_output(['icacls', str(account)], text=True))
            with patch('tesla_vpn.win32.is_admin', return_value=True): repair_account_permissions(root)
            self.assertIn('(I)', subprocess.check_output(['icacls', str(account)], text=True))
            self.assertEqual(identity.read_bytes(), b'preserve-key')
