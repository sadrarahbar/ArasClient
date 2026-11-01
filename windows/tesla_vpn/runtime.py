"""Private runtime files and native-core plans; no shell commands from imports."""
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import socket
import sys
from .profiles import Profile, private_write, validate_arguments


def resources():
    return Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[1]))


def state_root():
    return Path(os.environ.get("LOCALAPPDATA", str(Path.home() / "AppData/Local"))) / "TeslaVpn"


def free_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


@dataclass
class Plan:
    argv: list[str]
    env: dict[str, str]
    cwd: str

    def encode(self): return {"argv": self.argv, "env": self.env, "cwd": self.cwd}


def prepare(profile: Profile, port: int, root: Path, cores: Path | None = None):
    cores = cores or resources() / "cores"
    work = root / "accounts" / hashlib.sha256(json.dumps(profile.encode(), sort_keys=True).encode()).hexdigest()
    work.mkdir(parents=True, mode=0o700, exist_ok=True); work.chmod(0o700)
    env = {"HOME": str(work), "PATH": str(cores) + os.pathsep + os.environ.get("PATH", "")}
    if profile.kind == "aether":
        payload = profile.data
        args = list(payload["arguments"])
        validate_arguments(args)
        internal = free_port()
        while internal == port: internal = free_port()
        args = [a.replace("%socks_port%", str(port)).replace("%aether_port%", str(internal)) for a in args]
        args[args.index("--bind") + 1] = f"127.0.0.1:{internal if '--psiphon' in args else port}"
        if "--psiphon" in args:
            if "--psiphon-bind" not in args: args += ["--psiphon-bind", f"127.0.0.1:{port}"]
            else: args[args.index("--psiphon-bind") + 1] = f"127.0.0.1:{port}"
        for key, filename in [("AETHER_CONFIG", "aether.toml"), ("AETHER_WG_CONFIG", "aether-wg.toml"),
                              ("AETHER_MASQUE_CONFIG", "aether-masque.toml")]:
            env[key] = str(work / filename)
        if payload.get("identity"):
            target = work / ("aether-masque.toml" if payload["protocol"] == "masque" else "aether-wg.toml")
            if not target.exists(): private_write(target, payload["identity"].encode())
        env["AETHER_PSIPHON_BIN"] = str(cores / "psiphon-tunnel-core.exe")
        env["AETHER_PSIPHON_SERVER_ENTRIES"] = str(cores / "psiphon-servers.txt")
        binary = cores / "aether.exe"
    else:
        config = json.loads(json.dumps(profile.data))
        config["inbounds"] = [{"tag": "socks", "listen": "127.0.0.1", "port": port, "protocol": "socks",
                               "settings": {"auth": "noauth", "udp": True}}]
        config["log"] = {"loglevel": "warning"}
        config.pop("api", None)
        target = work / "xray.json"
        private_write(target, json.dumps(config).encode())
        env["XRAY_LOCATION_ASSET"] = str(cores)
        binary = cores / "xray.exe"
        args = ["run", "-c", str(target)]
    if not binary.is_file():
        raise ValueError("Native cores are missing. Run windows/setup.ps1 first.")
    return Plan([str(binary), *args], env, str(work))


def command(*args):
    if getattr(sys, "frozen", False): return [sys.executable, *args]
    return [sys.executable, str(resources() / "main.py"), *args]
