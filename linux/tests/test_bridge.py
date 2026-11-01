import asyncio
from pathlib import Path
import sys
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tesla_vpn.http_bridge import handle, relay

class BridgeTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.destinations = []
        async def target(r, w):
            request = await r.readuntil(b'\r\n\r\n')
            self.assertTrue(request.startswith(b'GET /path?test=1 HTTP/1.1'))
            w.write(b'HTTP/1.1 200 OK\r\nContent-Length: 2\r\n\r\nOK'); await w.drain(); w.close()
        self.origin = await asyncio.start_server(target, '127.0.0.1', 0)
        origin_port = self.origin.sockets[0].getsockname()[1]
        async def socks(r, w):
            await r.readexactly(3); w.write(b'\x05\x00'); await w.drain()
            self.assertEqual(await r.readexactly(4), b'\x05\x01\x00\x03')
            size = (await r.readexactly(1))[0]; host = await r.readexactly(size)
            await r.readexactly(2); self.destinations.append(host)
            rr, ww = await asyncio.open_connection('127.0.0.1', origin_port)
            w.write(b'\x05\x00\x00\x01\x7f\x00\x00\x01\x00\x01'); await w.drain()
            tasks = [asyncio.create_task(relay(r,ww)),asyncio.create_task(relay(rr,w))]
            await asyncio.wait(tasks,return_when=asyncio.FIRST_COMPLETED)
            for t in tasks:t.cancel()
            await asyncio.gather(*tasks,return_exceptions=True)
            w.close();ww.close()
        self.socks = await asyncio.start_server(socks, '127.0.0.1', 0)
        port = self.socks.sockets[0].getsockname()[1]
        self.bridge = await asyncio.start_server(lambda r,w:handle(r,w,port),'127.0.0.1',0)

    async def asyncTearDown(self):
        for s in [self.bridge,self.socks,self.origin]:s.close();await s.wait_closed()

    async def test_http_proxy_uses_remote_dns_and_origin_form(self):
        r,w=await asyncio.open_connection('127.0.0.1',self.bridge.sockets[0].getsockname()[1])
        w.write(b'GET http://not-local.invalid/path?test=1 HTTP/1.1\r\nHost: not-local.invalid\r\n\r\n');await w.drain()
        response=await asyncio.wait_for(r.read(),3)
        self.assertTrue(response.endswith(b'OK'));self.assertEqual(self.destinations,[b'not-local.invalid'])
        w.close();await w.wait_closed()

    async def test_connect_relays_bytes_after_success(self):
        r,w=await asyncio.open_connection('127.0.0.1',self.bridge.sockets[0].getsockname()[1])
        w.write(b'CONNECT remote.invalid:443 HTTP/1.1\r\nHost: remote.invalid\r\n\r\n');await w.drain()
        self.assertIn(b'200 Connection Established',await r.readuntil(b'\r\n\r\n'))
        w.write(b'GET /path?test=1 HTTP/1.1\r\nHost: remote.invalid\r\n\r\n');await w.drain()
        self.assertTrue((await asyncio.wait_for(r.read(),3)).endswith(b'OK'))
        w.close();await w.wait_closed()
