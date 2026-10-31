#!/usr/bin/env python3
"""Nekoray custom core for portable ArasClient Aether exports (Python 3.11+)."""
import hashlib
import json
import os
from pathlib import Path
import re
import socket
import sys
import tomllib


def prepare(payload, root):
    if payload.get("version") != 1 or payload.get("protocol") not in ("wg", "masque"):
        raise ValueError("Unsupported Aras Aether export version or protocol")
    identity = payload.get("identity")
    if not isinstance(identity, str):
        raise ValueError("Missing WARP identity")
    account = tomllib.loads(identity)
    required = ("device_id", "key_pem", "cert_pem", "ipv4") if payload["protocol"] == "masque" else (
        "device_id", "wg_private_key", "wg_peer_public_key", "ipv4"
    )
    if not all(isinstance(account.get(k), str) and account[k].strip() for k in required):
        raise ValueError("Incomplete WARP identity; reconnect the profile before exporting")
    arguments = payload.get("arguments")
    if not isinstance(arguments, list) or not arguments or not all(isinstance(a, str) for a in arguments):
        raise ValueError("Invalid Aether arguments")
    forbidden = {"--upstream", "--config", "--masque-config", "--wg-config",
                 "--tor", "--psiphon-only", "--tor-only", "--tor-reverse"}
    if forbidden.intersection(arguments):
        raise ValueError("This profile requires an unsupported helper or custom file")
    if any("%aether_port%" in a for a in arguments):
        while True:
            with socket.socket() as listener:
                listener.bind(("127.0.0.1", 0))
                internal_port = listener.getsockname()[1]
            if f"127.0.0.1:{internal_port}" not in arguments:
                break
        arguments = [a.replace("%aether_port%", str(internal_port)) for a in arguments]
    if arguments.count("--bind") != 1:
        raise ValueError("A single loopback listener is required")
    index = arguments.index("--bind")
    bind = arguments[index + 1] if index + 1 < len(arguments) else ""
    if not re.fullmatch(r"127\.0\.0\.1:[0-9]{1,5}", bind) or not 1 <= int(bind.rsplit(":", 1)[1]) <= 65535:
        raise ValueError("Nekoray must substitute a valid local SOCKS port")
    if "--protocol" not in arguments or arguments[arguments.index("--protocol") + 1] != payload["protocol"]:
        raise ValueError("Protocol does not match the exported identity")
    work = root / "accounts" / hashlib.sha256(identity.encode()).hexdigest()
    work.mkdir(parents=True, mode=0o700, exist_ok=True)
    work.chmod(0o700)
    filename = "aether-masque.toml" if payload["protocol"] == "masque" else "aether-wg.toml"
    target = work / filename
    # Keep renewals performed by Aether on subsequent starts, rather than restoring stale keys.
    if not target.exists():
        fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w") as stream:
            stream.write(identity)
    target.chmod(0o600)
    return work, arguments


def main():
    if len(sys.argv) != 2:
        raise ValueError("Usage: aras-aether /path/to/nekoray-generated-config.json")
    root = Path(__file__).resolve().parent
    config = Path(sys.argv[1])
    config.chmod(0o600)
    payload = json.loads(config.read_text())
    work, arguments = prepare(payload, root)
    binary = root / "aether"
    if not os.access(binary, os.X_OK):
        raise ValueError("Aether is missing; run tools/nekoray/install.py")
    env = os.environ.copy()
    # Never inherit identity paths or flags from another Aether installation.
    env = {k: v for k, v in env.items() if not k.startswith("AETHER_")}
    env.pop("RUST_LOG", None)
    env.update({"HOME": str(work), "AETHER_CONFIG": str(work / "aether.toml"),
                "AETHER_MASQUE_CONFIG": str(work / "aether-masque.toml"),
                "AETHER_WG_CONFIG": str(work / "aether-wg.toml")})
    if "--psiphon" in arguments or "--psiphon-reverse" in arguments:
        psiphon = root / "psiphon-tunnel-core"
        if not os.access(psiphon, os.X_OK):
            raise ValueError("Missing Psiphon binary")
        env["AETHER_PSIPHON_BIN"] = str(psiphon)
        entries = root / "psiphon-servers.txt"
        if entries.is_file():
            env["AETHER_PSIPHON_SERVER_ENTRIES"] = str(entries)
    os.chdir(work)
    # No shell; Nekoray owns this process and can stop/restart it normally.
    os.execve(binary, [str(binary), *arguments], env)


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError, KeyError, IndexError):
        # JSON/TOML exceptions can include the sensitive source. Do not echo them.
        print("Aras Aether: invalid export or missing helper. Re-export a connected standalone WG/MASQUE profile and check the Linux installation.", file=sys.stderr)
        sys.exit(1)
