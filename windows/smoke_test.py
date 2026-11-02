"""Run on a real Windows runner: native parsers, Wintun lifecycle, packaged GUI."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time

ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT))
from tesla_vpn.tun import tun_config


def run(args,**kwargs):
    r=subprocess.run([str(x) for x in args],capture_output=True,text=True,timeout=45,**kwargs)
    if r.returncode:raise RuntimeError('Smoke command failed: '+Path(args[0]).name+'\n'+r.stdout+r.stderr)
    return r


def packaged_data_path(exe, state):
    """A real Xray+HTTP bridge round trip, entirely on loopback, no VPN credentials."""
    import socket, threading
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
    from tesla_vpn.profiles import Profile, private_write
    from tesla_vpn.runtime import prepare, free_port
    from tesla_vpn.win32 import private_directory
    class Origin(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200);self.send_header('Content-Length','11');self.end_headers();self.wfile.write(b'TESLA-CI-OK')
        def log_message(self,*args):pass
    private_directory(state)
    origin=ThreadingHTTPServer(('127.0.0.1',0),Origin)
    threading.Thread(target=origin.serve_forever,daemon=True).start()
    socks_port,http_port=free_port(),free_port()
    while socks_port==http_port:http_port=free_port()
    profile=Profile('CI loopback only','xray',{'outbounds':[{'protocol':'freedom','tag':'proxy'}]})
    plan=prepare(profile,socks_port,state,exe.parent/'_internal/cores')
    request=state/'session.json';private_write(request,json.dumps({'plan':plan.encode(),'port':socks_port,'mode':'proxy'}).encode())
    backend=bridge=None
    def listener(port):
        deadline=time.monotonic()+15
        while time.monotonic()<deadline:
            try:
                with socket.create_connection(('127.0.0.1',port),timeout=.2):return
            except OSError:time.sleep(.1)
        raise RuntimeError('Packaged helper did not open its listener.')
    try:
        backend=subprocess.Popen([str(exe),'--backend-run',str(request)],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
        listener(socks_port)
        bridge=subprocess.Popen([str(exe),'--http-bridge',str(socks_port),str(http_port)],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
        listener(http_port)
        with socket.create_connection(('127.0.0.1',http_port),timeout=10) as sock:
            port=origin.server_port
            sock.sendall(f'GET http://127.0.0.1:{port}/ HTTP/1.1\r\nHost: 127.0.0.1:{port}\r\nConnection: close\r\n\r\n'.encode())
            response=b''
            while chunk:=sock.recv(8192):response+=chunk
        if not response.endswith(b'TESLA-CI-OK'):raise RuntimeError('Packaged HTTP/SOCKS data path failed.')
        print('Packaged Xray + HTTP bridge successfully relay a real local request')
    finally:
        for child in [bridge,backend]:
            if child and child.poll() is None:
                child.stdin.close()
                try:child.wait(timeout=12)
                except subprocess.TimeoutExpired:child.kill();child.wait();raise RuntimeError('Packaged helper did not stop on parent EOF.')
        origin.shutdown();origin.server_close()
    for port in [socks_port,http_port]:
        try:
            with socket.create_connection(('127.0.0.1',port),timeout=.2):raise RuntimeError('Listener survived helper shutdown.')
        except OSError:pass
    print('Packaged helpers close listeners and child processes on parent EOF')


def main():
    import struct
    exe_path=ROOT.parent/'artifacts/windows/TeslaVpn/TeslaVpn.exe'
    image=exe_path.read_bytes();pe=struct.unpack_from('<I',image,0x3c)[0]
    if struct.unpack_from('<H',image,pe+24+68)[0]!=2:
        raise RuntimeError('Application must use the GUI subsystem, not a console.')
    print('EXE has the windowless GUI subsystem; no console is allocated')
    cores=ROOT/'cores'
    for name,flag in [('aether.exe','--version'),('xray.exe','version'),('sing-box.exe','version')]:
        run([cores/name,flag]);print(name+' executes on Windows')
    with tempfile.TemporaryDirectory() as tmp:
        temp=Path(tmp);config=temp/'tun.json';config.write_text(json.dumps(tun_config(12345,cores)))
        run([cores/'sing-box.exe','check','-c',config],cwd=str(cores))
        print('TUN configuration accepted by bundled sing-box')
        from tesla_vpn.win32 import is_admin
        if not is_admin():raise RuntimeError('The Windows build runner must allow the native Wintun test.')
        # Prove driver loading and cleanup without touching the runner's default
        # routes/DNS or requiring a real user VPN identity.
        c=tun_config(12345,cores);c['inbounds'][0]['auto_route']=False;c['inbounds'][0]['strict_route']=False
        c['inbounds'][0]['interface_name']='TeslaVpnCI'
        config.write_text(json.dumps(c))
        from tesla_vpn.win32 import Job
        job=Job();child=None
        try:
            child=job.spawn([str(cores/'sing-box.exe'),'run','-c',str(config)],cwd=str(cores),
                stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
            for _ in range(30):
                if child.poll() is not None:raise RuntimeError('Wintun did not start: '+child.stdout.read().decode(errors='replace'))
                result=run(['powershell','-NoProfile','-Command',"@(Get-NetAdapter -IncludeHidden -Name TeslaVpnCI -ErrorAction SilentlyContinue).Count"])
                if result.stdout.strip()=='1':break
                time.sleep(.3)
            else:raise RuntimeError('Wintun adapter was not created.')
            print('Wintun adapter created without changing system routing')
        finally:
            job.close()
            if child:child.wait(timeout=15)
        result=run(['powershell','-NoProfile','-Command',"@(Get-NetAdapter -IncludeHidden -Name TeslaVpnCI -ErrorAction SilentlyContinue).Count"])
        if result.stdout.strip()!='0':raise RuntimeError('Wintun adapter did not disappear after supervisor exit.')
        print('Wintun adapter cleaned up after Job Object close')
        exe=ROOT.parent/'artifacts/windows/TeslaVpn/TeslaVpn.exe'
        packaged_data_path(exe,temp/'data-path-state')
        fixture=temp/'profile.txt';fixture.write_text('aether://?protocol=masque#CI-no-credentials')
        image=ROOT.parent/'artifacts/windows/preview.png'
        run([exe,'--state-root',temp/'state','--profile',fixture,'--screenshot',image],env=dict(os.environ,QT_QPA_PLATFORM='offscreen'))
        from PIL import Image
        with Image.open(image) as im:
            if im.width<451 or im.height<852:raise RuntimeError('Packaged GUI screenshot is incomplete.')
        print('Packaged EXE imports a profile and renders the UI')
        # No account, private key, session or recovery data may enter the package.
        for p in exe.parent.rglob('*'):
            if p.is_file() and (p.suffix.lower() in ['.toml','.pem','.key'] or p.name in ['profile.json','session.json','proxy-recovery.json']):
                raise RuntimeError('Private runtime file in bundle: '+p.name)
        print('Package privacy scan passed')

if __name__=='__main__':main()
