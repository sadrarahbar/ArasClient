"""Use the actual packaged sing-box engine to check DNS routing without root/TUN."""
import asyncio
import json
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from tesla_vpn.tun import tun_config
from tesla_vpn.runtime import free_port

CORE=Path(__file__).resolve().parents[1]/'cores/sing-box'

@unittest.skipUnless(CORE.exists(),'native core not downloaded')
class DNSRoutingTests(unittest.IsolatedAsyncioTestCase):
    async def run_router(self,old_rule=False):
        observed=[]
        async def upstream(r,w):
            try:
                version,n=await r.readexactly(2);await r.readexactly(n)
                w.write(b'\x05\x00');await w.drain()
                header=await r.readexactly(4)
                hostsize={1:4,4:16}.get(header[3])
                if header[3]==3:hostsize=(await r.readexactly(1))[0]
                host=await r.readexactly(hostsize);port=int.from_bytes(await r.readexactly(2),'big')
                observed.append((header[1],port))
                w.write(b'\x05\x05\x00\x01'+b'\x00'*6);await w.drain()
            except asyncio.IncompleteReadError:pass
            finally:w.close()
        server=await asyncio.start_server(upstream,'127.0.0.1',0)
        port=free_port();config=tun_config(server.sockets[0].getsockname()[1],1000)
        config['inbounds']=[{'type':'socks','tag':'tun-in','listen':'127.0.0.1','listen_port':port,'sniff':False}]
        if old_rule:config['route']['rules']=[{'protocol':'dns','outbound':'dns-out'}]
        client=None
        with tempfile.TemporaryDirectory() as tmp:
            f=Path(tmp)/'config.json';f.write_text(json.dumps(config))
            process=subprocess.Popen([str(CORE),'run','-c',str(f)],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
            try:
                for _ in range(30):
                    try:r,client=await asyncio.open_connection('127.0.0.1',port);break
                    except OSError:await asyncio.sleep(.05)
                self.assertIsNotNone(client)
                client.write(b'\x05\x01\x00');await client.drain();self.assertEqual(await r.readexactly(2),b'\x05\x00')
                client.write(b'\x05\x03\x00\x01'+b'\x00'*6);await client.drain()
                reply=await r.readexactly(4)
                self.assertEqual(reply[1],0)
                if reply[3]==1:address=socket.inet_ntoa(await r.readexactly(4))
                else:raise AssertionError('Expected IPv4 UDP listener')
                destination_port=int.from_bytes(await r.readexactly(2),'big')
                packet=(b'\x00\x00\x00\x01'+socket.inet_aton('1.1.1.1')+b'\x00\x35'+
                    b'\x12\x34\x01\x00\x00\x01\x00\x00\x00\x00\x00\x00'+b'\x07youtube\x03com\x00\x00\x01\x00\x01')
                with socket.socket(socket.AF_INET,socket.SOCK_DGRAM) as s:s.sendto(packet,(address,destination_port))
                for _ in range(40):
                    if observed:break
                    await asyncio.sleep(.05)
            finally:
                if client:client.close();await client.wait_closed()
                process.terminate();process.wait(timeout=3)
                server.close();await server.wait_closed()
        return observed

    async def test_dns_without_sniffing_goes_to_encrypted_tcp_dns(self):
        observed=await self.run_router()
        self.assertIn((1,443),observed)
        self.assertNotIn((3,0),observed)

    async def test_old_protocol_only_rule_used_unsupported_udp_path(self):
        observed=await self.run_router(old_rule=True)
        self.assertTrue(any(command==3 for command,port in observed))
