import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from pathlib import Path
import sys,tempfile,time
import unittest
from unittest.mock import MagicMock
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from PyQt6.QtWidgets import QApplication
from PyQt6.QtNetwork import QNetworkReply
from tesla_vpn.engine import Engine
app=QApplication.instance() or QApplication([])

class Reply:
    def __init__(self,country):self.country=country
    def attribute(self,key):return 200
    def error(self):return QNetworkReply.NetworkError.NoError
    def readAll(self):return ('ip=not-logged\nloc='+self.country+'\n').encode()
    def deleteLater(self):pass

class EgressTests(unittest.TestCase):
    def test_direct_tun_country_must_match_its_verified_proxy_country(self):
        with tempfile.TemporaryDirectory() as tmp:
            e=Engine(Path(tmp));e.state='checking';e.mode='tun';e.proxy_country='DE';e.probe_started=time.monotonic()
            e._probe_done(Reply('IR'),'startup-direct',True,0)
            self.assertEqual(e.state,'error');self.assertIn('exit differs',e.message)

    def test_verified_tun_country_is_visible_without_storing_ip(self):
        with tempfile.TemporaryDirectory() as tmp:
            e=Engine(Path(tmp));e.state='checking';e.mode='tun';e.proxy_country='DE';e.probe_started=time.monotonic()
            e._start_bridge=MagicMock()
            e._probe_done(Reply('DE'),'startup-direct',True,0)
            self.assertEqual(e.state,'connected');self.assertIn('Exit: DE',e.message)
            self.assertNotIn('not-logged',(Path(tmp)/'status.json').read_text())

    def test_each_probe_clears_pooled_connections_before_switching_proxy(self):
        with tempfile.TemporaryDirectory() as tmp:
            e=Engine(Path(tmp));e.net=MagicMock()
            e._probe('startup-direct',direct=True)
            e.net.clearConnectionCache.assert_called_once()
            self.assertLess([x[0] for x in e.net.mock_calls].index('clearConnectionCache'),[x[0] for x in e.net.mock_calls].index('get'))
            e.probe_timer.stop()
