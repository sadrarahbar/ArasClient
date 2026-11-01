from pathlib import Path
import json
import sys
import tempfile
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from tesla_vpn.tun import read_request,tun_config

class TunTests(unittest.TestCase):
    def test_world_readable_request_is_rejected_before_commands(self):
        import os
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'request.json';p.write_text('{}');p.chmod(0o644)
            with self.assertRaises(ValueError):read_request(p,os.getuid())

    def test_symlink_request_is_rejected(self):
        import os
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'actual';p.write_text('{}');p.chmod(0o600)
            link=Path(tmp)/'request';link.symlink_to(p)
            with self.assertRaises(OSError):read_request(link,os.getuid())

    def test_tun_dns_is_tunneled_and_both_ip_families_are_routed(self):
        c=tun_config(1080,1000)
        self.assertTrue(c['inbounds'][0]['auto_route'])
        self.assertIn('inet6_address',c['inbounds'][0])
        self.assertEqual(c['dns']['servers'][0]['detour'],'proxy')
        self.assertEqual(c['outbounds'][0]['server_port'],1080)

class HelperLifecycleTests(unittest.TestCase):
    def run_helper(self, fail_second_rule=False, core_failed=False):
        import io,os,subprocess
        from types import SimpleNamespace
        from unittest.mock import patch,MagicMock
        from contextlib import redirect_stdout
        from tesla_vpn import tun
        calls=[]
        def checked(args,**kw):
            calls.append(args)
            if fail_second_rule and '-6' in args and 'add' in args:raise subprocess.CalledProcessError(1,args)
            return SimpleNamespace(stdout=b'[]',returncode=0)
        def unverified(args,**kw):
            calls.append(args)
            return SimpleNamespace(returncode=1,stdout=b'')
        child=MagicMock();child.pid=999999;child.poll.return_value=1 if core_failed else None
        stdin=io.StringIO('stop\n');out=io.StringIO()
        d={'port':1080,'plan':{'argv':['core'],'env':{},'cwd':'/tmp'}}
        with tempfile.TemporaryDirectory() as runtime:
            original_tempfile=tempfile.TemporaryDirectory
            def tempdir(**kw):return original_tempfile(dir=runtime)
            with patch.object(tun.os,'geteuid',return_value=0),patch.dict(tun.os.environ,{'PKEXEC_UID':'1000'}), \
                 patch.object(tun.pwd,'getpwuid',return_value=SimpleNamespace(pw_dir='/tmp',pw_name='test')), \
                 patch.object(tun.shutil,'which',side_effect=lambda name:'/usr/sbin/'+name), \
                 patch.object(tun,'read_request',return_value=d),patch.object(tun,'run',side_effect=checked), \
                 patch.object(tun.subprocess,'run',side_effect=unverified),patch.object(tun.subprocess,'Popen',return_value=child), \
                 patch.object(tun,'stop_child') as stop,patch.object(tun.signal,'signal'), \
                 patch.object(tun.select,'select',return_value=([stdin],[],[])),patch.object(tun.sys,'stdin',stdin), \
                 patch.object(tun.tempfile,'TemporaryDirectory',side_effect=tempdir),redirect_stdout(out):
                result=tun.main('/private/session.json')
                stopped=[x.args[0] for x in stop.call_args_list]
        return result,calls,out.getvalue(),stopped,child

    def test_stop_restores_both_route_rules_and_owned_nft_table(self):
        result,calls,events,stopped,child=self.run_helper()
        self.assertEqual(result,0);self.assertIn(child,stopped)
        deleted=[x for x in calls if 'rule' in x and 'del' in x]
        self.assertEqual(len(deleted),2)
        self.assertTrue(any(x[-4:]==['delete','table','inet','tesla_vpn_1000'] for x in calls))
        self.assertIn('stopped',events)

    def test_partial_setup_failure_also_removes_first_route_rule(self):
        result,calls,events,_,_=self.run_helper(fail_second_rule=True)
        self.assertEqual(result,1)
        deleted=[x for x in calls if 'rule' in x and 'del' in x]
        self.assertEqual(len(deleted),1);self.assertIn('-4',deleted[0])
        self.assertTrue(any('delete' in x and 'tesla_vpn_1000' in x for x in calls))

    def test_core_failure_cleans_up_without_claiming_tun_ready(self):
        result,calls,events,stopped,child=self.run_helper(core_failed=True)
        self.assertEqual(result,1);self.assertIn('backend-failed',events)
        self.assertNotIn('tun-ready',events);self.assertIn(child,stopped)

    def test_native_cores_drop_root_before_execution(self):
        from unittest.mock import patch
        from tesla_vpn.tun import drop_identity
        actions=[]
        with patch('os.setsid',side_effect=lambda:actions.append('session')), \
             patch('os.setgroups',side_effect=lambda g:actions.append(('groups',g))), \
             patch('os.setgid',side_effect=lambda g:actions.append(('gid',g))), \
             patch('os.setuid',side_effect=lambda u:actions.append(('uid',u))), \
             patch('ctypes.CDLL'):
            drop_identity(1000,61000)()
        self.assertEqual(actions,['session',('groups',[]),('gid',61000),('uid',1000)])

class RouteReadinessTests(unittest.TestCase):
    def test_existing_interface_with_direct_routes_is_not_ready(self):
        from unittest.mock import patch
        from types import SimpleNamespace
        from tesla_vpn.tun import routes_use_tun
        with patch('tesla_vpn.tun.run',return_value=SimpleNamespace(stdout=b'[{"dev":"wlan0"}]')):
            self.assertFalse(routes_use_tun('/usr/sbin/ip',1000))

    def test_ipv6_bypass_prevents_green_status(self):
        from unittest.mock import patch
        from types import SimpleNamespace
        from tesla_vpn.tun import routes_use_tun
        results=[SimpleNamespace(stdout=b'[{"dev":"tesla1000"}]'),SimpleNamespace(stdout=b'[{"dev":"eth0"}]')]
        with patch('tesla_vpn.tun.run',side_effect=results):self.assertFalse(routes_use_tun('/usr/sbin/ip',1000))

    def test_both_families_must_use_tesla_interface(self):
        from unittest.mock import patch
        from types import SimpleNamespace
        from tesla_vpn.tun import routes_use_tun
        with patch('tesla_vpn.tun.run',return_value=SimpleNamespace(stdout=b'[{"dev":"tesla1000"}]')) as run:
            self.assertTrue(routes_use_tun('/usr/sbin/ip',1000));self.assertEqual(run.call_count,2)
