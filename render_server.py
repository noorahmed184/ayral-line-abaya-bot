# -*- coding: utf-8 -*-
"""
AERAL LINE: one Render Web Service for the Streamlit website + Telegram webhook.

Required environment variables:
- TELEGRAM_BOT_TOKEN
- OPENAI_API_KEY
Optional:
- TELEGRAM_WEBHOOK_SECRET (letters, numbers, underscore, hyphen only)
- STAFF_EMAIL, SENDER_EMAIL, GMAIL_APP_PASSWORD
- INSTAGRAM_URL, INSTAGRAM_HANDLE, WHATSAPP_NUMBER

Start Command on Render:  python render_server.py
"""

import asyncio
import logging
import os
import sys
from pathlib import Path

import aiohttp
from aiohttp import web

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("aeral-line")

ROOT = Path(__file__).resolve().parent
STREAMLIT_HOST = "127.0.0.1"
STREAMLIT_PORT = 8501

http_session = None
streamlit_process = None


async def streamlit_proxy(request):
    if http_session is None:
        return web.Response(status=503, text="Website is starting...")

    target = f"http://{STREAMLIT_HOST}:{STREAMLIT_PORT}{request.rel_url}"

    if request.headers.get("Upgrade", "").lower() == "websocket":
        headers = {
            k: v for k, v in request.headers.items()
            if k.lower() not in {
                "connection", "upgrade", "host",
                "sec-websocket-key", "sec-websocket-version",
                "sec-websocket-extensions", "sec-websocket-accept",
                "sec-websocket-protocol"
            }
        }

        protocols = [
            p.strip() for p in
            request.headers.get("Sec-WebSocket-Protocol", "").split(",")
            if p.strip()
        ]

        try:
            async with http_session.ws_connect(
                target, headers=headers, protocols=protocols
            ) as backend:
                frontend = web.WebSocketResponse(
                    protocols=(backend.protocol,) if backend.protocol else ()
                )
                await frontend.prepare(request)

                async def forward(source, destination):
                    async for msg in source:
                        if msg.type == aiohttp.WSMsgType.TEXT:
                            await destination.send_str(msg.data)
                        elif msg.type == aiohttp.WSMsgType.BINARY:
                            await destination.send_bytes(msg.data)
                        elif msg.type == aiohttp.WSMsgType.CLOSE:
                            await destination.close()
                            break

                await asyncio.gather(
                    forward(frontend, backend),
                    forward(backend, frontend)
                )
                return frontend

        except Exception:
            log.exception("Websocket proxy error")
            return web.Response(status=502, text="Websocket unavailable")

    headers = {
        k: v for k, v in request.headers.items()
        if k.lower() not in {
            "connection", "keep-alive", "host",
            "accept-encoding", "transfer-encoding"
        }
    }

    try:
        async with http_session.request(
            request.method,
            target,
            headers=headers,
            data=await request.read(),
            allow_redirects=False
        ) as response:
            return web.Response(
                body=await response.read(),
                status=response.status,
                headers={
                    k: v for k, v in response.headers.items()
                    if k.lower() not in {
                        "connection", "transfer-encoding",
                        "content-encoding", "content-length"
                    }
                }
            )

    except Exception:
        log.exception("Website proxy error")
        return web.Response(status=502, text="Website unavailable")


async def startup(app):
    global http_session, streamlit_process

    streamlit_file = ROOT / "stapp.py"

    if not streamlit_file.exists():
        raise RuntimeError("stapp.py was not found")

    streamlit_process = await asyncio.create_subprocess_exec(
        sys.executable,
        "-m", "streamlit", "run", str(streamlit_file),
        "--server.port", str(STREAMLIT_PORT),
        "--server.address", STREAMLIT_HOST,
        "--server.headless", "true",
        "--server.enableCORS", "false",
        "--server.enableXsrfProtection", "false",
        cwd=str(ROOT)
    )

    for _ in range(120):
        if streamlit_process.returncode is not None:
            raise RuntimeError("Streamlit stopped during startup")

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"http://{STREAMLIT_HOST}:{STREAMLIT_PORT}/_stcore/health",
                    timeout=aiohttp.ClientTimeout(total=2)
                ) as response:
                    if response.status < 500:
                        break
        except Exception:
            pass

        await asyncio.sleep(1)
    else:
        raise RuntimeError("Streamlit did not start")

    http_session = aiohttp.ClientSession(
        timeout=aiohttp.ClientTimeout(total=300)
    )

    log.info("Website is ready")


async def cleanup(app):
    global http_session, streamlit_process

    if http_session:
        await http_session.close()

    if streamlit_process and streamlit_process.returncode is None:
        streamlit_process.terminate()
        try:
            await asyncio.wait_for(streamlit_process.wait(), timeout=10)
        except asyncio.TimeoutError:
            streamlit_process.kill()
            await streamlit_process.wait()


def create_app():
    app = web.Application()
    app.router.add_get("/healthz", lambda request: web.Response(text="ok"))
    app.router.add_route("*", "/{tail:.*}", streamlit_proxy)
    app.on_startup.append(startup)
    app.on_cleanup.append(cleanup)
    return app


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "10000"))
    web.run_app(create_app(), host="0.0.0.0", port=port)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "10000"))
    log.info("Opening web server on 0.0.0.0:%s", port)
    web.run_app(create_app(), host="0.0.0.0", port=port)
