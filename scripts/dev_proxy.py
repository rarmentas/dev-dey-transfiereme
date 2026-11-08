#!/usr/bin/env python3
"""Proxy de desarrollo: /api/* → Django :8001; resto → Flutter :9100."""
from __future__ import annotations

import argparse
import asyncio
import sys

try:
    from aiohttp import ClientSession, WSMsgType, web
except ImportError:
    print(
        "Falta aiohttp. Ejecute ./scripts/upgrade.sh o: "
        "backend/.venv/bin/pip install aiohttp",
        file=sys.stderr,
    )
    sys.exit(1)

DJANGO_UPSTREAM = "http://127.0.0.1:8001"
FLUTTER_UPSTREAM = "http://127.0.0.1:9100"
HOP_HEADERS = {
    "connection",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailers",
    "transfer-encoding",
    "upgrade",
}


def upstream_for_path(path: str) -> str:
    if path.startswith("/api"):
        return DJANGO_UPSTREAM
    return FLUTTER_UPSTREAM


def filtered_headers(headers) -> dict[str, str]:
    out: dict[str, str] = {}
    for key, value in headers.items():
        if key.lower() not in HOP_HEADERS:
            out[key] = value
    return out


async def proxy_http(request: web.Request) -> web.StreamResponse:
    upstream_base = upstream_for_path(request.rel_url.path)
    target = upstream_base + str(request.rel_url)
    body = await request.read()

    async with ClientSession() as session:
        async with session.request(
            request.method,
            target,
            headers=filtered_headers(request.headers),
            data=body if body else None,
            allow_redirects=False,
        ) as upstream_resp:
            response_headers = filtered_headers(upstream_resp.headers)
            response = web.StreamResponse(
                status=upstream_resp.status,
                headers=response_headers,
            )
            await response.prepare(request)
            async for chunk in upstream_resp.content.iter_chunked(65536):
                await response.write(chunk)
            return response


async def proxy_ws(request: web.Request) -> web.WebSocketResponse:
    upstream_base = upstream_for_path(request.rel_url.path)
    target = upstream_base.replace("http://", "ws://") + str(request.rel_url)

    client_ws = web.WebSocketResponse()
    await client_ws.prepare(request)

    async with ClientSession() as session:
        async with session.ws_connect(
            target,
            headers=filtered_headers(request.headers),
        ) as upstream_ws:
            async def client_to_upstream() -> None:
                async for msg in client_ws:
                    if msg.type == WSMsgType.TEXT:
                        await upstream_ws.send_str(msg.data)
                    elif msg.type == WSMsgType.BINARY:
                        await upstream_ws.send_bytes(msg.data)
                    elif msg.type in (WSMsgType.CLOSE, WSMsgType.ERROR):
                        break

            async def upstream_to_client() -> None:
                async for msg in upstream_ws:
                    if msg.type == WSMsgType.TEXT:
                        await client_ws.send_str(msg.data)
                    elif msg.type == WSMsgType.BINARY:
                        await client_ws.send_bytes(msg.data)
                    elif msg.type in (WSMsgType.CLOSE, WSMsgType.ERROR):
                        break

            await asyncio.gather(client_to_upstream(), upstream_to_client())

    return client_ws


async def handle(request: web.Request) -> web.StreamResponse:
    if request.headers.get("Upgrade", "").lower() == "websocket":
        return await proxy_ws(request)
    return await proxy_http(request)


def main() -> None:
    parser = argparse.ArgumentParser(description="Proxy de desarrollo Cody")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()

    app = web.Application()
    app.router.add_route("*", "/{path:(.*)}", handle)

    web.run_app(app, host=args.host, port=args.port, print=lambda *_: None)


if __name__ == "__main__":
    main()
