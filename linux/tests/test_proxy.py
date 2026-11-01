import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from tesla_vpn.system_proxy import SystemProxy

class ProxyTests(unittest.TestCase):
    def test_restore_preserves_changes_made_by_user_after_connection(self):
        with tempfile.TemporaryDirectory() as tmp:
            proxy=SystemProxy(Path(tmp))
            data={'desktop':'kde','old':{'ProxyType':'0','httpProxy':'old'},'new':{'ProxyType':'1','httpProxy':'tesla'}}
            proxy.backup.write_text(json.dumps(data))
            current={'ProxyType':'1','httpProxy':'user-changed'};writes=[]
            with patch.object(proxy,'_read',side_effect=lambda d,k:current[k]),patch.object(proxy,'_write',side_effect=lambda d,k,v:writes.append((k,v))),patch.object(proxy,'_reload'):
                proxy.restore()
            self.assertEqual(writes,[('ProxyType','0')]);self.assertFalse(proxy.backup.exists())

    def test_failed_restore_retains_recovery_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            proxy=SystemProxy(Path(tmp));proxy.backup.write_text(json.dumps({'desktop':'kde','old':{'ProxyType':'0'},'new':{'ProxyType':'1'}}))
            with patch.object(proxy,'_read',side_effect=OSError('unavailable')):
                with self.assertRaises(OSError):proxy.restore()
            self.assertTrue(proxy.backup.exists())

class PlasmaGTKCompatibilityTests(unittest.TestCase):
    def targets(self):
        return ({'desktop':'kde','old':{'ProxyType':'0','httpProxy':'old-kde'},'new':{'httpProxy':'new-kde','ProxyType':'1'}},
                {'desktop':'gnome','old':{'org.gnome.system.proxy/mode':"'none'",'host':'old-gtk'},'new':{'host':'new-gtk','org.gnome.system.proxy/mode':"'manual'"}})

    def test_plasma_updates_gtk_too_and_restores_both_backends(self):
        import os
        kde,gtk=self.targets()
        values={(d['desktop'],k):v for d in [kde,gtk] for k,v in d['old'].items()};original=values.copy()
        with tempfile.TemporaryDirectory() as tmp:
            p=SystemProxy(Path(tmp))
            with patch.dict(os.environ,{'XDG_CURRENT_DESKTOP':'KDE'}),patch('tesla_vpn.system_proxy.shutil.which',return_value='/usr/bin/gsettings'), \
                 patch('tesla_vpn.system_proxy.run',return_value='\n'.join({s for s,k in p.GNOME_KEYS})), \
                 patch.object(p,'_snapshot_kde',return_value=kde),patch.object(p,'_snapshot_gnome',return_value=gtk), \
                 patch.object(p,'_read',side_effect=lambda d,k:values[d['desktop'],k]), \
                 patch.object(p,'_write',side_effect=lambda d,k,v:values.__setitem__((d['desktop'],k),v)),patch.object(p,'_reload'):
                p.activate(1200,1300)
                self.assertEqual(values['kde','ProxyType'],'1')
                self.assertEqual(values['gnome','org.gnome.system.proxy/mode'],"'manual'")
                self.assertEqual(len(json.loads(p.backup.read_text())['targets']),2)
                p.restore();self.assertEqual(values,original)
                self.assertFalse(p.backup.exists())

    def test_failure_in_gtk_rolls_back_already_applied_kde_settings(self):
        import os
        kde,gtk=self.targets();values={(d['desktop'],k):v for d in [kde,gtk] for k,v in d['old'].items()};original=values.copy()
        failed=[False]
        def write(d,k,v):
            if d['desktop']=='gnome' and v=="'manual'" and not failed[0]:failed[0]=True;raise OSError('write failed')
            values[d['desktop'],k]=v
        with tempfile.TemporaryDirectory() as tmp:
            p=SystemProxy(Path(tmp))
            with patch.dict(os.environ,{'XDG_CURRENT_DESKTOP':'KDE'}),patch('tesla_vpn.system_proxy.shutil.which',return_value='/usr/bin/gsettings'), \
                 patch('tesla_vpn.system_proxy.run',return_value='\n'.join({s for s,k in p.GNOME_KEYS})), \
                 patch.object(p,'_snapshot_kde',return_value=kde),patch.object(p,'_snapshot_gnome',return_value=gtk), \
                 patch.object(p,'_read',side_effect=lambda d,k:values[d['desktop'],k]),patch.object(p,'_write',side_effect=write),patch.object(p,'_reload'):
                with self.assertRaises(ValueError):p.activate(1200,1300)
                self.assertEqual(values,original)
                self.assertFalse(p.backup.exists())
