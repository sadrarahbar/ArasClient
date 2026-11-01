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


def main():
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
