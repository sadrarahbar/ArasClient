"""Parse imports without executing config text; keep exactly one validated profile."""
from __future__ import annotations
import base64
import configparser
from dataclasses import dataclass
import json
import os
from pathlib import Path
import tempfile
import tomllib
from urllib.parse import parse_qs, unquote, urlsplit

MAX_IMPORT = 8 * 1024 * 1024

class ImportError(ValueError):
    pass

@dataclass(frozen=True)
class Profile:
    name: str
    kind: str
    data: dict

    def encode(self):
        return {"version": 1, "name": self.name, "kind": self.kind, "data": self.data}


def decode64(text: str) -> bytes:
    return base64.b64decode(text + "=" * (-len(text) % 4), altchars=b"-_", validate=True)


def parse_import(text: str) -> Profile:
    if len(text.encode()) > MAX_IMPORT:
        raise ImportError("Configuration is too large (maximum 8 MB).")
    text = text.strip().lstrip("\ufeff")
    if not text:
        raise ImportError("No configuration was found.")
    try:
        if text.startswith(("{", "[")):
            if text.startswith("[Interface]"):
                return wireguard_profile(text)
            obj = json.loads(text)
            if isinstance(obj, list):
                obj = next((x for x in obj if isinstance(x, dict) and "outbounds" in x), None)
            if isinstance(obj, dict) and obj.get("version") == 1 and "identity" in obj:
                return aether_export(obj, "Aether")
            if isinstance(obj, dict) and obj.get("core") == "aras-aether":
                return aether_export(json.loads(obj["cs"]), obj.get("name", "Aether"))
            if isinstance(obj, dict) and obj.get("outbounds"):
                return xray_profile(obj)
            raise ImportError("This JSON is not a supported Xray or Aether configuration.")
        lines = text.splitlines()
        if len(lines) > 1:
            for line in lines:
                try:
                    return parse_import(line)
                except (ValueError, TypeError, KeyError):
                    continue
            raise ImportError("No supported configuration was found in this file.")
        if text.startswith("nekoray://custom#"):
            bean = json.loads(decode64(text.split("#", 1)[1]))
            if bean.get("core") != "aras-aether":
                raise ImportError("This Nekoray link uses a different external core.")
            return aether_export(json.loads(bean["cs"]), bean.get("name", "Aether"))
        if text.startswith("aether://"):
            return aether_link(text)
        if text.startswith(("vless://", "vmess://", "trojan://", "ss://", "socks://")):
            return proxy_link(text)
        # Subscription files sometimes wrap links in base64, never fetch remote URLs implicitly.
        if "://" not in text:
            decoded = decode64(text).decode("utf-8")
            if "://" in decoded:
                return parse_import(decoded)
        raise ImportError("Import an Aether/Nekoray link, proxy link, Xray JSON or WireGuard file.")
    except ImportError:
        raise
    except (ValueError, TypeError, KeyError, IndexError, UnicodeError, configparser.Error):
        # Never put decoded identities, JSON excerpts or keys in errors.
        raise ImportError("The configuration is invalid or incomplete.") from None


# Only arguments emitted by our Android exporter; path/command injection is not accepted.
VALUE_FLAGS = {
    "--bind", "--protocol", "--scan", "--noize", "--ip", "--peer", "--log-level", "--dns",
    "--exit-loc", "--psiphon-bind", "--psiphon-mode", "--psiphon-region", "--api-address",
    "--api-sni", "--api-host", "--masque-sni", "--fragment-size", "--fragment-delay",
    "--ech", "--ech-dns", "--ech-domain", "--tls-ciphers", "--tls-groups", "--tls-sigalgs",
    "--tls13-ciphers", "--tls-key-shares", "--psiphon-cdn-ips", "--psiphon-cdn-sni",
}
BOOL_FLAGS = {"--h2", "--h3", "--quick-reconnect", "--no-quick-reconnect", "--psiphon",
              "--psiphon-reverse", "--fragment", "--tls-verify", "--no-profile-retry",
              "--disable-grease", "--enable-grease-sigalgs", "--disable-psiphon-bundled-entries"}


def validate_arguments(args):
    if not isinstance(args, list) or not args or not all(isinstance(x, str) for x in args):
        raise ImportError("Missing Aether arguments.")
    i = 0
    while i < len(args):
        flag = args[i]
        if flag in BOOL_FLAGS:
            i += 1
        elif flag in VALUE_FLAGS and i + 1 < len(args) and not args[i + 1].startswith("--"):
            i += 2
        else:
            raise ImportError("This profile uses an unsupported Aether option.")
    if args.count("--bind") != 1 or args.count("--protocol") != 1:
        raise ImportError("A single Aether tunnel is required.")


def aether_export(obj, name):
    if obj.get("version") != 1 or obj.get("protocol") not in ("wg", "masque"):
        raise ImportError("Unsupported Aether export.")
    account = tomllib.loads(obj["identity"])
    required = ("device_id", "key_pem", "cert_pem", "ipv4") if obj["protocol"] == "masque" else (
        "device_id", "wg_private_key", "wg_peer_public_key", "ipv4")
    if not all(isinstance(account.get(x), str) and account[x].strip() for x in required):
        raise ImportError("Incomplete WARP identity. Export a connected profile from Android.")
    args = obj.get("arguments")
    validate_arguments(args)
    if args[args.index("--protocol") + 1] != obj["protocol"]:
        raise ImportError("The identity and tunnel protocol do not match.")
    return Profile(str(name)[:160], "aether", obj)


def aether_link(text):
    u = urlsplit(text)
    q = parse_qs(u.query)
    get = lambda key, default="": q.get(key, [default])[0]
    protocol = get("protocol", "wg")
    if protocol not in ("wg", "masque") or get("tor", "off") != "off":
        raise ImportError("This Linux version supports single-hop Aether WG/MASQUE, optionally with Psiphon.")
    args = ["--bind", "127.0.0.1:%socks_port%", "--protocol", protocol,
            "--scan", get("scan", "balanced"), "--ip", get("ip", "v4"), "--log-level", "warn"]
    if get("noize", "auto") != "auto":
        args += ["--noize", get("noize")]
    if u.hostname:
        if not u.port:
            raise ImportError("An explicit endpoint needs a port.")
        host = f"[{u.hostname}]" if ":" in u.hostname else u.hostname
        args += ["--peer", f"{host}:{u.port}"]
    if protocol == "masque":
        args += ["--h2" if get("transport", "h3") == "h2" else "--h3"]
    for query, flag in [("dns", "--dns"), ("exit_loc", "--exit-loc"), ("api_address", "--api-address"),
                        ("api_sni", "--api-sni"), ("api_host", "--api-host"), ("masque_sni", "--masque-sni")]:
        if get(query): args += [flag, get(query)]
    if get("fragment") == "1": args += ["--fragment"]
    psiphon = get("psiphon", "off")
    if psiphon not in ("off", "chain", "reverse"):
        raise ImportError("Unsupported Psiphon mode.")
    if psiphon != "off":
        args += ["--psiphon" if psiphon == "chain" else "--psiphon-reverse"]
        if psiphon == "chain":
            args[args.index("--bind") + 1] = "127.0.0.1:%aether_port%"
            args += ["--psiphon-bind", "127.0.0.1:%socks_port%"]
        for query, flag in [("region", "--psiphon-region"), ("psiphon_mode", "--psiphon-mode")]:
            if get(query): args += [flag, get(query)]
    validate_arguments(args)
    return Profile(unquote(u.fragment)[:160] or "Aether", "aether",
                   {"version": 1, "protocol": protocol, "arguments": args})


def xray_profile(obj):
    outbounds = obj.get("outbounds")
    if not isinstance(outbounds, list) or not outbounds or not all(isinstance(x, dict) and x.get("protocol") for x in outbounds):
        raise ImportError("Missing Xray outbounds.")
    return Profile(str(obj.get("remarks", "VPN configuration"))[:160], "xray", obj)


def proxy_link(text):
    u = urlsplit(text)
    name = unquote(u.fragment)[:160] or u.scheme.upper()
    if u.scheme == "vmess":
        d = json.loads(decode64(text[8:]))
        outbound = {"protocol": "vmess", "settings": {"vnext": [{"address": d["add"], "port": int(d["port"]),
                    "users": [{"id": d["id"], "alterId": int(d.get("aid", 0)), "security": d.get("scy", "auto")}]}]}}
        q = {"type": d.get("net", "tcp"), "security": d.get("tls") or "none", "sni": d.get("sni", ""),
             "host": d.get("host", ""), "path": d.get("path", ""), "fp": d.get("fp", "chrome")}
        name = d.get("ps") or name
    else:
        q = {k: v[0] for k, v in parse_qs(u.query).items()}
        if not u.hostname or not u.port:
            raise ImportError("The proxy address or port is missing.")
        server = {"address": u.hostname, "port": u.port}
        if u.scheme == "vless":
            outbound = {"protocol": "vless", "settings": {"vnext": [{**server, "users": [{"id": unquote(u.username or ""),
                        "encryption": "none", "flow": q.get("flow", "")}]}]}}
        elif u.scheme == "trojan":
            outbound = {"protocol": "trojan", "settings": {"servers": [{**server, "password": unquote(u.username or "")} ]}}
        elif u.scheme == "socks":
            users = [{"user": unquote(u.username), "pass": unquote(u.password or "")}] if u.username else []
            outbound = {"protocol": "socks", "settings": {"servers": [{**server, "users": users}]}}
        elif u.scheme == "ss":
            if q.get("plugin"):
                raise ImportError("Shadowsocks plugins are not supported.")
            auth = unquote(u.username or "")
            if u.password is not None: method, password = auth, unquote(u.password)
            else: method, password = decode64(auth).decode().split(":", 1)
            outbound = {"protocol": "shadowsocks", "settings": {"servers": [{**server, "method": method, "password": password}]}}
        else:
            raise ImportError("Unsupported proxy link.")
    if outbound["protocol"] in ("vless", "vmess", "trojan"):
        network = q.get("type", "tcp")
        security = q.get("security", "tls" if u.scheme == "trojan" else "none")
        stream = {"network": network, "security": security}
        if security == "reality":
            stream["realitySettings"] = {"serverName": q.get("sni", ""), "fingerprint": q.get("fp", "chrome"),
                "publicKey": q.get("pbk", ""), "shortId": q.get("sid", ""), "spiderX": q.get("spx", "")}
        elif security == "tls":
            stream["tlsSettings"] = {"serverName": q.get("sni", ""), "fingerprint": q.get("fp", "chrome"),
                                    "allowInsecure": False}
            if q.get("alpn"): stream["tlsSettings"]["alpn"] = q["alpn"].split(",")
        elif security != "none":
            raise ImportError("Unsupported transport security.")
        if network == "ws": stream["wsSettings"] = {"path": q.get("path", "/"), "headers": {"Host": q.get("host", "")}}
        elif network == "grpc": stream["grpcSettings"] = {"serviceName": q.get("serviceName", "")}
        elif network in ("xhttp", "splithttp"):
            stream["xhttpSettings"] = {"path": q.get("path", "/"), "host": q.get("host", ""), "mode": q.get("mode", "auto")}
        elif network not in ("tcp", "raw"):
            raise ImportError("Import full Xray JSON for this transport.")
        outbound["streamSettings"] = stream
    outbound["tag"] = "proxy"
    return xray_profile({"remarks": name, "outbounds": [outbound]})


def wireguard_profile(text):
    c = configparser.ConfigParser(interpolation=None, strict=True)
    c.read_string(text)
    interface, peer = c["Interface"], c["Peer"]
    item = {"publicKey": peer["PublicKey"], "endpoint": peer["Endpoint"],
            "allowedIPs": [x.strip() for x in peer.get("AllowedIPs", "0.0.0.0/0,::/0").split(",")]}
    if peer.get("PresharedKey"): item["preSharedKey"] = peer["PresharedKey"]
    settings = {"secretKey": interface["PrivateKey"], "address": [x.strip() for x in interface["Address"].split(",")],
                "mtu": int(interface.get("MTU", "1280")), "noKernelTun": True, "peers": [item]}
    return xray_profile({"remarks": "WireGuard", "outbounds": [{"tag": "proxy", "protocol": "wireguard", "settings": settings}]})


def private_write(path: Path, data: bytes):
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    path.parent.chmod(0o700)
    fd, tmp = tempfile.mkstemp(prefix=".new-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data); f.flush(); os.fsync(f.fileno())
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp): os.unlink(tmp)


class ProfileStore:
    def __init__(self, root: Path):
        self.path = root / "profile.json"

    def load(self):
        if not self.path.exists(): return None
        try:
            obj = json.loads(self.path.read_text())
            if obj.get("version") != 1 or obj.get("kind") not in ("aether", "xray"):
                raise ValueError()
            return Profile(obj["name"], obj["kind"], obj["data"])
        except (ValueError, KeyError, TypeError):
            raise ImportError("Saved configuration could not be read. Import it again.") from None

    def import_text(self, text):
        profile = parse_import(text)
        private_write(self.path, json.dumps(profile.encode(), ensure_ascii=False).encode())
        return profile
