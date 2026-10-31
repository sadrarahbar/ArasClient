import importlib.util
from pathlib import Path
import tempfile
import unittest

spec = importlib.util.spec_from_file_location("runner", Path(__file__).with_name("aras-aether.py"))
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


class RunnerTest(unittest.TestCase):
    def payload(self):
        return {"version": 1, "protocol": "masque", "identity":
                'device_id="fixture"\nkey_pem="fake-key"\ncert_pem="fake-cert"\nipv4="172.16.0.2"\n',
                "arguments": ["--bind", "127.0.0.1:23456", "--protocol", "masque", "--h2"]}

    def test_private_identity_and_preserve_renewals(self):
        with tempfile.TemporaryDirectory() as root:
            work, args = runner.prepare(self.payload(), Path(root))
            account = work / "aether-masque.toml"
            self.assertEqual(account.stat().st_mode & 0o777, 0o600)
            self.assertEqual(work.stat().st_mode & 0o777, 0o700)
            account.write_text("renewed-identity")
            runner.prepare(self.payload(), Path(root))
            self.assertEqual(account.read_text(), "renewed-identity")
            self.assertEqual(args, self.payload()["arguments"])

    def test_reject_unsubstituted_or_public_listener(self):
        for bind in ["127.0.0.1:%socks_port%", "0.0.0.0:1080", "127.0.0.1:0", "127.0.0.1:99999"]:
            payload = self.payload()
            payload["arguments"][1] = bind
            with self.assertRaises(ValueError):
                runner.prepare(payload, Path("/unused"))

    def test_reject_missing_key_and_external_dependency(self):
        payload = self.payload()
        payload["identity"] = 'device_id="fixture"'
        with self.assertRaises(ValueError):
            runner.prepare(payload, Path("/unused"))

    def test_psiphon_chain_uses_two_different_loopback_listeners(self):
        payload = self.payload()
        payload["arguments"] = ["--bind", "127.0.0.1:%aether_port%", "--protocol", "masque",
                                "--psiphon", "--psiphon-bind", "127.0.0.1:23456"]
        with tempfile.TemporaryDirectory() as root:
            _, args = runner.prepare(payload, Path(root))
            self.assertNotIn("%aether_port%", str(args))
            self.assertNotEqual("127.0.0.1:23456", args[1])
            self.assertIn("--psiphon", args)
        payload = self.payload()
        payload["arguments"] += ["--upstream", "socks5://127.0.0.1:1234"]
        with self.assertRaises(ValueError):
            runner.prepare(payload, Path("/unused"))


if __name__ == "__main__":
    unittest.main()
