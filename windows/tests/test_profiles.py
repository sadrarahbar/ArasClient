import base64
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tesla_vpn.profiles import ImportError, ProfileStore, parse_import
from tesla_vpn.runtime import prepare


def identity():
    return 'device_id="device"\nwg_private_key="private"\nwg_peer_public_key="public"\nipv4="172.16.0.2"\n'


def portable(args=None):
    return {"version": 1, "protocol": "wg", "identity": identity(), "arguments": args or [
        "--bind", "127.0.0.1:%socks_port%", "--protocol", "wg", "--scan", "balanced"]}


class ProfileTests(unittest.TestCase):
    def test_batch_keeps_first_valid_and_invalid_import_preserves_previous(self):
        with tempfile.TemporaryDirectory() as root:
            store = ProfileStore(Path(root))
            store.import_text('invalid\naether://?protocol=wg#first\naether://?protocol=masque#second')
            self.assertEqual(store.load().name, "first")
            before = store.path.read_bytes()
            with self.assertRaises(ImportError): store.import_text('not a config')
            self.assertEqual(store.path.read_bytes(), before)
            if sys.platform != 'win32': self.assertEqual(store.path.stat().st_mode & 0o777, 0o600)
            self.assertEqual(store.path.parent.stat().st_mode & 0o777, 0o700)
            store.import_text('aether://?protocol=masque#replacement')
            self.assertEqual(store.load().name, "replacement")
            self.assertEqual(len(list(Path(root).glob('profile*.json'))), 1)

    def test_nekoray_export_carries_identity_and_arguments(self):
        bean = {"core": "aras-aether", "name": "portable", "cs": json.dumps(portable())}
        link = 'nekoray://custom#' + base64.urlsafe_b64encode(json.dumps(bean).encode()).decode().rstrip('=')
        p = parse_import(link)
        self.assertEqual(p.name, 'portable'); self.assertEqual(p.data['identity'], identity())

    def test_external_commands_and_paths_are_rejected(self):
        for bad in ['--psiphon-bin', '--config', '--upstream', '--tor-pt']:
            payload = portable(portable()['arguments'] + [bad, '/tmp/untrusted'])
            with self.assertRaises(ImportError): parse_import(json.dumps(payload))

    def test_runtime_rebinds_final_proxy_and_preserves_renewed_identity(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); cores = root / 'cores'; cores.mkdir()
            core = cores / 'aether.exe'; core.write_text('#!/bin/sh\n'); core.chmod(0o755)
            args = portable()['arguments'] + ['--psiphon', '--psiphon-bind', '127.0.0.1:%socks_port%']
            p = parse_import(json.dumps(portable(args)))
            plan = prepare(p, 12345, root / 'state', cores)
            self.assertNotEqual(plan.argv[plan.argv.index('--bind')+1], '127.0.0.1:12345')
            self.assertEqual(plan.argv[plan.argv.index('--psiphon-bind')+1], '127.0.0.1:12345')
            account = Path(plan.env['AETHER_WG_CONFIG']); account.write_text('renewed')
            prepare(p, 12346, root / 'state', cores)
            self.assertEqual(account.read_text(), 'renewed')
            if sys.platform != 'win32': self.assertEqual(account.stat().st_mode & 0o777, 0o600)

    def test_aether_h2_psiphon_route_is_preserved(self):
        p = parse_import('aether://?protocol=masque&transport=h2&psiphon=chain&region=DE&noize=off#test')
        self.assertIn('--h2', p.data['arguments']); self.assertIn('--psiphon', p.data['arguments'])
        self.assertIn('DE', p.data['arguments'])

    def test_vless_reality_and_ws_options(self):
        p = parse_import('vless://id@example.com:443?security=reality&sni=example.org&pbk=key&sid=abcd&flow=xtls-rprx-vision#reality')
        stream = p.data['outbounds'][0]['streamSettings']
        self.assertEqual(stream['realitySettings']['publicKey'], 'key')
        self.assertEqual(stream['realitySettings']['serverName'], 'example.org')

    def test_wireguard_configuration(self):
        p = parse_import('[Interface]\nPrivateKey=test\nAddress=172.16.0.2/32\n[Peer]\nPublicKey=peer\nEndpoint=1.2.3.4:2408\n')
        self.assertEqual(p.data['outbounds'][0]['protocol'], 'wireguard')

    def test_error_does_not_contain_private_content(self):
        with self.assertRaises(ImportError) as error: parse_import('{"secret":"DO_NOT_LOG",')
        self.assertNotIn('DO_NOT_LOG', str(error.exception))

    def test_wrapped_subscription(self):
        text = 'aether://?protocol=wg#first\naether://?protocol=masque#second'
        p = parse_import(base64.b64encode(text.encode()).decode())
        self.assertEqual(p.name,'first')

if __name__ == '__main__': unittest.main()
