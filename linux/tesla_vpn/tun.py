"""Small privileged network supervisor. Imported profiles/cores run with the user's UID.

Only sing-box, nft and ip run as root. Native cores receive a private, unassigned
primary GID so their sockets can bypass TUN without excluding other user programs.
The supervisor owns the rules and removes them on stdin EOF, stop, or child failure.
"""
from __future__ import annotations
import ctypes
import grp
import json
import os
from pathlib import Path
import pwd
import select
import shutil
import signal
import socket
import stat
import subprocess
import sys
import tempfile
import time
from .runtime import resources


def tun_config(port, uid):
    return {
        "log": {"level": "warn"},
        "dns": {"servers": [{"tag": "secure", "address": "https://1.1.1.1/dns-query", "detour": "proxy"}],
                "strategy": "ipv4_only"},
        "inbounds": [{"type": "tun", "tag": "tun-in", "interface_name": f"tesla{uid}",
            "inet4_address": "172.29.255.1/30", "inet6_address": "fdfe:7465:736c::1/126",
            "mtu": 1400, "auto_route": True, "strict_route": True, "stack": "gvisor"}],
        "outbounds": [{"type": "socks", "tag": "proxy", "server": "127.0.0.1", "server_port": port,
                       "version": "5"}, {"type": "dns", "tag": "dns-out"}],
        "route": {"rules": [{"port": 53, "outbound": "dns-out"}],
                  "final": "proxy", "auto_detect_interface": True},
    }


def routes_use_tun(ip, uid):
    """Do not announce readiness until unmarked IPv4 and IPv6 routes enter our TUN."""
    expected = f"tesla{uid}"
    for family, target in [("-4", "1.1.1.1"), ("-6", "2606:4700:4700::1111")]:
        try:
            routes = json.loads(run([ip, family, "-j", "route", "get", target]).stdout)
            if not routes or routes[0].get("dev") != expected: return False
        except (OSError, ValueError, subprocess.SubprocessError): return False
    return True


def emit(event):
    print(json.dumps({"event": event}), flush=True)


def run(args, **kwargs):
    return subprocess.run(args, capture_output=True, check=True, timeout=8, **kwargs)


def drop_identity(uid, gid):
    def apply():
        os.setsid()
        os.setgroups([])
        os.setgid(gid)
        os.setuid(uid)
        # Set after dropping privileges, because setuid clears the parent-death signal.
        ctypes.CDLL(None).prctl(1, signal.SIGTERM, 0, 0, 0)
    return apply


def stop_child(child):
    if child is None: return
    try:
        os.killpg(child.pid, signal.SIGINT)
        child.wait(timeout=4)
    except subprocess.TimeoutExpired:
        os.killpg(child.pid, signal.SIGKILL); child.wait(timeout=2)
    except ProcessLookupError:
        pass


def read_request(path, uid):
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(fd) as stream:
        info = os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_uid != uid or info.st_mode & 0o077 or info.st_size > 1024 * 1024:
            raise ValueError("Unsafe session request")
        d = json.load(stream)
    port = d.get("port")
    if not isinstance(port, int) or not 1024 <= port <= 65535: raise ValueError("Invalid port")
    plan = d.get("plan", {})
    argv = plan.get("argv", [])
    if not argv or not isinstance(argv, list) or not all(isinstance(a, str) for a in argv):
        raise ValueError("Invalid core plan")
    if Path(argv[0]).resolve() not in [(resources() / "cores" / n).resolve() for n in ("aether", "xray")]:
        raise ValueError("Unknown core")
    return d


def main(request_path):
    if os.geteuid() != 0:
        emit("administrator-required"); return 1
    uid = int(os.environ.get("PKEXEC_UID", "-1"))
    if uid <= 0: emit("invalid-user"); return 1
    account = pwd.getpwuid(uid)
    core = router = None
    rules = []
    table_created = False
    nft = shutil.which("nft")
    ip = shutil.which("ip")
    if not nft or not ip: emit("network-tools-missing"); return 1
    mark = 0x74530000 + uid % 65536
    table = f"tesla_vpn_{uid}"
    priority = 1100 + uid % 1000
    stopping = False
    def cancel(*_):
        nonlocal stopping
        stopping = True
    signal.signal(signal.SIGTERM, cancel); signal.signal(signal.SIGINT, cancel)
    try:
        d = read_request(request_path, uid)
        # Refuse overlapping owned state rather than deleting rules belonging to a live session.
        if subprocess.run([nft, "list", "table", "inet", table], capture_output=True).returncode == 0:
            emit("tun-already-active"); return 1
        for family in ("-4", "-6"):
            existing = json.loads(run([ip, family, "-j", "rule", "show"]).stdout)
            if any(r.get("priority") == priority for r in existing):
                emit("routing-conflict"); return 1
        occupied = {g.gr_gid for g in grp.getgrall()}
        gid = next(g for g in range(60000 + uid % 3000, 65000) if g not in occupied)
        script = (f"add table inet {table}\n"
                  f"add chain inet {table} output {{ type route hook output priority mangle; policy accept; }}\n"
                  f"add rule inet {table} output meta skgid {gid} meta mark set {mark}\n")
        run([nft, "-f", "-"], input=script.encode()); table_created = True
        for family in ("-4", "-6"):
            args = [ip, family, "rule", "add", "priority", str(priority), "fwmark", str(mark), "lookup", "main"]
            run(args); rules.append([ip, family, "rule", "del", "priority", str(priority), "fwmark", str(mark), "lookup", "main"])
        plan = d["plan"]
        env = {"PATH": "/usr/bin:/bin", "HOME": account.pw_dir, "USER": account.pw_name,
               "SSL_CERT_FILE": "/etc/ssl/certs/ca-certificates.crt"}
        env.update({k: v for k, v in plan.get("env", {}).items() if k.startswith("AETHER_") or k in ("HOME", "XRAY_LOCATION_ASSET")})
        core = subprocess.Popen(plan["argv"], cwd=plan["cwd"], env=env,
                                stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                preexec_fn=drop_identity(uid, gid))
        emit("backend-started")
        enabled = False
        deadline = time.monotonic() + 180
        with tempfile.TemporaryDirectory(prefix=f"tesla-vpn-{uid}-", dir="/run") as temp:
            config = Path(temp) / "tun.json"
            config.write_text(json.dumps(tun_config(d["port"], uid))); config.chmod(0o600)
            while not stopping:
                if core.poll() is not None: emit("backend-failed"); return 1
                readable, _, _ = select.select([sys.stdin], [], [], .2)
                if readable:
                    command = sys.stdin.readline()
                    if not command or command.strip() == "stop": break
                    if command.strip() == "enable" and not enabled:
                        router = subprocess.Popen([str(resources() / "cores/sing-box"), "run", "-c", str(config)],
                            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                            start_new_session=True, env={"PATH": "/usr/bin:/bin", "HOME": "/root"})
                        enabled = True
                        routing_deadline = time.monotonic() + 15
                if router:
                    if router.poll() is not None: emit("tun-failed"); return 1
                    if enabled and Path(f"/sys/class/net/tesla{uid}").exists() and routes_use_tun(ip, uid):
                        emit("tun-ready"); enabled = False
                    elif enabled and time.monotonic() > routing_deadline:
                        emit("tun-routing-failed"); return 1
                if time.monotonic() > deadline and router is None:
                    emit("connection-timeout"); return 1
        return 0
    except Exception:
        emit("tun-setup-failed")
        return 1
    finally:
        # Stop TUN before its upstream so no default route points to a dead proxy.
        stop_child(router)
        for args in reversed(rules):
            try: subprocess.run(args, capture_output=True, timeout=5)
            except (OSError, subprocess.SubprocessError): pass
        if table_created:
            try: subprocess.run([nft, "delete", "table", "inet", table], capture_output=True, timeout=5)
            except (OSError, subprocess.SubprocessError): pass
        stop_child(core)
        emit("stopped")
