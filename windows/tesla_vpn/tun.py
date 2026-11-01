"""Windows native-core supervisor; Wintun routes/DNS belong to sing-box's lifetime."""
import json
import os
from pathlib import Path
import queue
import subprocess
import sys
import threading
import time
from .profiles import private_write
from .runtime import resources
from .win32 import Job, is_admin


def tun_config(port, cores=None):
    cores = cores or resources() / 'cores'
    return {
        'log': {'level': 'warn'},
        'dns': {'servers': [{'type': 'https', 'tag': 'secure', 'server': '1.1.1.1',
            'server_port': 443, 'path': '/dns-query', 'tls': {'enabled': True, 'server_name': 'cloudflare-dns.com'},
            'detour': 'proxy'}], 'final': 'secure', 'strategy': 'ipv4_only'},
        'inbounds': [{'type': 'tun', 'tag': 'tun-in', 'interface_name': 'TeslaVpn',
            'address': ['172.29.255.1/30', 'fdfe:7465:736c::1/126'], 'mtu': 1400,
            'auto_route': True, 'strict_route': True, 'stack': 'gvisor'}],
        'outbounds': [{'type': 'socks', 'tag': 'proxy', 'server': '127.0.0.1', 'server_port': port, 'version': '5'},
                      {'type': 'direct', 'tag': 'direct'}],
        'route': {'auto_detect_interface': True, 'final': 'proxy', 'rules': [
            # Exact bundled executable paths, never all Python/user/browser traffic.
            {'process_path': [str((cores / name).resolve()) for name in
                ['aether.exe','psiphon-tunnel-core.exe','lyrebird.exe','xray.exe']], 'action': 'route', 'outbound': 'direct'},
            {'port': 53, 'action': 'hijack-dns'}]},
    }


def routes_use_tun():
    """Query the actual Windows forwarding table for both IP families."""
    import ctypes, socket, struct
    from ctypes import wintypes
    api = ctypes.WinDLL('iphlpapi', use_last_error=True)
    api.GetBestInterfaceEx.argtypes = [ctypes.c_void_p, ctypes.POINTER(wintypes.DWORD)]
    api.ConvertInterfaceIndexToLuid.argtypes = [wintypes.DWORD, ctypes.POINTER(ctypes.c_uint64)]
    api.ConvertInterfaceLuidToAlias.argtypes = [ctypes.POINTER(ctypes.c_uint64), wintypes.LPWSTR, ctypes.c_size_t]
    for family, address in [(socket.AF_INET, '1.1.1.1'), (socket.AF_INET6, '2606:4700:4700::1111')]:
        raw = struct.pack('H', family) + b'\0\0'
        if family == socket.AF_INET: raw += socket.inet_pton(family,address) + b'\0'*8
        else: raw += b'\0'*4 + socket.inet_pton(family,address) + b'\0'*4
        sockaddr = ctypes.create_string_buffer(raw)
        index = wintypes.DWORD(); luid = ctypes.c_uint64(); alias = ctypes.create_unicode_buffer(257)
        if api.GetBestInterfaceEx(sockaddr, ctypes.byref(index)): return False
        if api.ConvertInterfaceIndexToLuid(index, ctypes.byref(luid)): return False
        if api.ConvertInterfaceLuidToAlias(ctypes.byref(luid), alias, 257): return False
        if alias.value != 'TeslaVpn': return False
    return True


def emit(event): print(json.dumps({'event': event}), flush=True)


def read_request(path):
    path = Path(path)
    if path.is_symlink() or path.stat().st_size > 1024 * 1024: raise ValueError('Invalid session request.')
    data = json.loads(path.read_text(encoding='utf-8'))
    plan = data['plan']; port = data['port']
    if type(port) is not int or not 1024 <= port <= 65535: raise ValueError('Invalid listener port.')
    argv = plan['argv']; cores = resources() / 'cores'
    if not isinstance(argv, list) or not argv or not all(isinstance(s,str) for s in argv): raise ValueError('Invalid plan.')
    if Path(argv[0]).resolve() not in [(cores/n).resolve() for n in ['aether.exe','xray.exe']]:
        raise ValueError('Unrecognized bundled core.')
    expected = path.parent / 'accounts'
    if not Path(plan['cwd']).resolve().is_relative_to(expected.resolve()): raise ValueError('Invalid account directory.')
    return data


def commands(stream, output):
    try:
        for line in stream:
            output.put(line.strip())
    finally: output.put('stop')


def stop_child(child):
    if child is not None and child.poll() is None:
        child.terminate()
        try: child.wait(timeout=5)
        except subprocess.TimeoutExpired: child.kill(); child.wait(timeout=5)


def main(path, with_tun=True):
    job = None; backend = router = None
    try:
        data = read_request(path)
        if with_tun and not is_admin(): emit('admin-required'); return 1
        job = Job(); plan = data['plan']
        env = {k:v for k,v in os.environ.items() if not k.startswith('AETHER_') and k not in ['LD_PRELOAD','RUST_LOG']}
        env.update(plan['env'])
        backend = job.spawn(plan['argv'], cwd=plan['cwd'], env=env,
            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        emit('backend-started')
        inbox = queue.Queue(); threading.Thread(target=commands,args=(sys.stdin,inbox),daemon=True).start()
        while backend.poll() is None:
            try: command = inbox.get(timeout=.15)
            except queue.Empty: command = ''
            if command == 'stop': return 0
            if command == 'enable' and with_tun and router is None:
                core = resources() / 'cores' / 'sing-box.exe'
                config = Path(path).parent / 'tun.json'
                private_write(config, json.dumps(tun_config(data['port'])).encode())
                router = job.spawn([str(core), 'run', '-c', str(config)], cwd=str(core.parent),
                    stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                deadline = time.monotonic() + 20
                while router.poll() is None and time.monotonic() < deadline:
                    if routes_use_tun(): break
                    if not inbox.empty():
                        if inbox.get() == 'stop': return 0
                    time.sleep(.25)
                else: emit('tun-routing-failed'); return 1
                emit('tun-ready')
            if router is not None and router.poll() is not None: emit('tun-failed'); return 1
        emit('backend-failed'); return 1
    except Exception:
        emit('tun-setup-failed' if with_tun else 'backend-failed'); return 1
    finally:
        stop_child(router); stop_child(backend)
        if job: job.close()
        if not with_tun:
            try:
                from .system_proxy import SystemProxy
                SystemProxy(Path(path).parent).restore()
            except Exception: pass  # snapshot is retained for next launch
