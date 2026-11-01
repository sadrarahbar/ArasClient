"""Loopback HTTP CONNECT/forward proxy over a SOCKS5 tunnel, with remote DNS."""
import asyncio
from urllib.parse import urlsplit


async def open_socks(host, port, proxy_port):
    reader, writer = await asyncio.open_connection("127.0.0.1", proxy_port)
    try:
        writer.write(b"\x05\x01\x00"); await writer.drain()
        if await reader.readexactly(2) != b"\x05\x00": raise OSError("SOCKS authentication failed")
        name = host.encode("idna")
        if len(name) > 255: raise OSError("Invalid host")
        writer.write(b"\x05\x01\x00\x03" + bytes([len(name)]) + name + port.to_bytes(2, "big"))
        await writer.drain()
        reply = await reader.readexactly(4)
        if reply[:2] != b"\x05\x00": raise OSError("SOCKS connection failed")
        length = {1: 4, 4: 16}.get(reply[3])
        if reply[3] == 3: length = (await reader.readexactly(1))[0]
        if length is None: raise OSError("Invalid SOCKS reply")
        await reader.readexactly(length + 2)
        return reader, writer
    except BaseException:
        writer.close()
        raise


async def relay(reader, writer):
    while chunk := await reader.read(65536):
        writer.write(chunk)
        await writer.drain()


async def handle(reader, writer, socks_port):
    upstream = None
    tasks = []
    try:
        header = await asyncio.wait_for(reader.readuntil(b"\r\n\r\n"), 15)
        lines = header.decode("iso-8859-1").split("\r\n")
        method, target, version = lines[0].split(" ", 2)
        if method == "CONNECT":
            url = urlsplit("//" + target)
            host, port = url.hostname, url.port or 443
        else:
            url = urlsplit(target)
            if url.scheme != "http": raise ValueError("HTTP URL required")
            host, port = url.hostname, url.port or 80
        if not host: raise ValueError("Host required")
        remote_reader, upstream = await asyncio.wait_for(open_socks(host, port, socks_port), 25)
        if method == "CONNECT":
            writer.write(b"HTTP/1.1 200 Connection Established\r\n\r\n"); await writer.drain()
        else:
            path = (url.path or "/") + ("?" + url.query if url.query else "")
            filtered = [l for l in lines[1:] if l and not l.lower().startswith(("proxy-connection:", "proxy-authorization:", "connection:"))]
            first = f"{method} {path} {version}\r\n" + "\r\n".join(filtered) + "\r\nConnection: close\r\n\r\n"
            upstream.write(first.encode("iso-8859-1")); await upstream.drain()
        tasks = [asyncio.create_task(relay(reader, upstream)), asyncio.create_task(relay(remote_reader, writer))]
        await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
    except (OSError, ValueError, asyncio.TimeoutError, asyncio.IncompleteReadError, asyncio.LimitOverrunError):
        try: writer.write(b"HTTP/1.1 502 Bad Gateway\r\nContent-Length: 0\r\nConnection: close\r\n\r\n"); await writer.drain()
        except OSError: pass
    finally:
        for task in tasks: task.cancel()
        if tasks: await asyncio.gather(*tasks, return_exceptions=True)
        writer.close()
        if upstream: upstream.close()


async def serve(socks_port, http_port):
    server = await asyncio.start_server(lambda r, w: handle(r, w, socks_port), "127.0.0.1", http_port)
    async with server: await server.serve_forever()
