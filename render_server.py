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
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
log = logging.getLogger("aeral-line")

# httpx logs every Telegram API URL, and that URL contains the bot token.
# Keep these loggers quiet so the token never lands in Render's logs.
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)

ROOT = Path(__file__).resolve().parent
STREAMLIT_HOST = "127.0.0.1"
STREAMLIT_PORT = 8501

# The Streamlit website file (app.py is the old initial code, not the website).
STREAMLIT_CANDIDATES = ("stapp.py",)

TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
BASE_URL = os.environ.get("RENDER_EXTERNAL_URL", "").rstrip("/")
WEBHOOK_SECRET = os.environ.get("TELEGRAM_WEBHOOK_SECRET", "").strip()

# Keep a separate conversation history for each Telegram chat.
telegram_bots = {}
telegram_app = None
http_session = None
streamlit_process = None


def find_streamlit_file():
    for name in STREAMLIT_CANDIDATES:
        path = ROOT / name
        if path.exists():
            return path
    raise RuntimeError(
        "Streamlit file not found. Looked for: " + ", ".join(STREAMLIT_CANDIDATES)
    )


def get_chat_bot(chat_id):
    if chat_id not in telegram_bots:
        from bot_core import AbayaBot
        telegram_bots[chat_id] = AbayaBot()
    return telegram_bots[chat_id]


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    telegram_bots.pop(chat_id, None)
    await update.effective_message.reply_text(
        "هلا فيج في أيرال لاين 🌸\nشلون أقدر أساعدج؟"
    )


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.effective_message
    chat_id = update.effective_chat.id
    text = (message.text or message.caption or "").strip()
    image_bytes = None

    if message.photo:
        photo_file = await message.photo[-1].get_file()
        image_bytes = bytes(await photo_file.download_as_bytearray())

    if not text and not image_bytes:
        return

    await context.bot.send_chat_action(chat_id=chat_id, action="typing")

    try:
        bot = await asyncio.to_thread(get_chat_bot, chat_id)
        answer, handoff = await asyncio.to_thread(bot.reply, text, image_bytes)
    except Exception:
        log.exception("Telegram bot reply failed")
        await message.reply_text("عذراً، صار خطأ. حاولي مرة ثانية 🌸")
        return

    await message.reply_text(answer or "حاولي مرة ثانية 🌸")

    if handoff:
        user = update.effective_user
        username = user.username or "No username"
        customer = f"تلقرام: {user.full_name} (@{username}) id={user.id}"
        try:
            from notifications import notify_staff
            await asyncio.to_thread(
                notify_staff, customer, handoff, text or "(صورة)"
            )
            await message.reply_text(
                f"🔔 تم تحويل المحادثة للموظفة: {handoff}"
            )
        except Exception:
            log.exception("Staff notification failed")


async def telegram_webhook(request: web.Request):
    expected = request.app["webhook_secret"]
    supplied = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
    if expected and supplied != expected:
        raise web.HTTPForbidden(text="Invalid webhook secret")

    try:
        payload = await request.json()
        update = Update.de_json(payload, telegram_app.bot)
        await telegram_app.update_queue.put(update)
    except Exception:
        log.exception("Could not accept Telegram update")
        raise web.HTTPBadRequest(text="Invalid Telegram update")

    return web.Response(text="ok")


async def healthz(request: web.Request):
    """Lightweight endpoint for UptimeRobot / Render health checks."""
    return web.Response(text="ok")


HOP_BY_HOP_HEADERS = {
    "connection", "keep-alive", "proxy-authenticate", "proxy-authorization",
    "te", "trailers", "transfer-encoding", "upgrade", "host",
}

# aiohttp sets these itself on the websocket handshake to Streamlit.
WS_HANDSHAKE_HEADERS = {
    "sec-websocket-key", "sec-websocket-version", "sec-websocket-extensions",
    "sec-websocket-accept", "sec-websocket-protocol",
}


async def streamlit_proxy(request: web.Request):
    """Forward website HTTP requests and Streamlit websocket traffic."""
    target = f"http://{STREAMLIT_HOST}:{STREAMLIT_PORT}{request.rel_url}"

    if request.headers.get("Upgrade", "").lower() == "websocket":
        headers = {
            k: v for k, v in request.headers.items()
            if k.lower() not in HOP_BY_HOP_HEADERS
            and k.lower() not in WS_HANDSHAKE_HEADERS
        }
        # Streamlit's browser client sends subprotocols such as
        # "streamlit, <token>". Pass them to Streamlit and accept the same one
        # that Streamlit picks, otherwise the websocket never connects.
        requested = [
            p.strip()
            for p in request.headers.get("Sec-WebSocket-Protocol", "").split(",")
            if p.strip()
        ]
        ws_front = None
        try:
            async with http_session.ws_connect(
                target, headers=headers, protocols=requested
            ) as ws_back:
                ws_front = web.WebSocketResponse(
                    protocols=(ws_back.protocol,) if ws_back.protocol else ()
                )
                await ws_front.prepare(request)

                async def front_to_back():
                    async for item in ws_front:
                        if item.type == aiohttp.WSMsgType.TEXT:
                            await ws_back.send_str(item.data)
                        elif item.type == aiohttp.WSMsgType.BINARY:
                            await ws_back.send_bytes(item.data)
                        elif item.type == aiohttp.WSMsgType.PING:
                            await ws_back.ping()
                        elif item.type == aiohttp.WSMsgType.PONG:
                            await ws_back.pong()
                        elif item.type == aiohttp.WSMsgType.CLOSE:
                            await ws_back.close()
                            break

                async def back_to_front():
                    async for item in ws_back:
                        if item.type == aiohttp.WSMsgType.TEXT:
                            await ws_front.send_str(item.data)
                        elif item.type == aiohttp.WSMsgType.BINARY:
                            await ws_front.send_bytes(item.data)
                        elif item.type == aiohttp.WSMsgType.PING:
                            await ws_front.ping()
                        elif item.type == aiohttp.WSMsgType.PONG:
                            await ws_front.pong()
                        elif item.type == aiohttp.WSMsgType.CLOSE:
                            await ws_front.close()
                            break

                await asyncio.gather(front_to_back(), back_to_front())
        except Exception:
            log.exception("Streamlit websocket proxy failed")
            if ws_front is None:
                return web.Response(
                    status=502, text="Streamlit websocket unavailable"
                )
            await ws_front.close()
        return ws_front

    # Ask Streamlit for an uncompressed response: aiohttp decompresses bodies
    # automatically, so forwarding "Content-Encoding: gzip" with a plain body
    # would break the page in the browser.
    headers = {
        k: v for k, v in request.headers.items()
        if k.lower() not in HOP_BY_HOP_HEADERS
        and k.lower() != "accept-encoding"
    }
    body = await request.read()

    async with http_session.request(
        request.method,
        target,
        headers=headers,
        data=body if body else None,
        allow_redirects=False,
    ) as response:
        response_body = await response.read()
        response_headers = {
            k: v for k, v in response.headers.items()
            if k.lower() not in HOP_BY_HOP_HEADERS
            and k.lower() not in ("content-encoding", "content-length")
        }
        return web.Response(
            body=response_body,
            status=response.status,
            headers=response_headers,
        )


async def start_background_services(app: web.Application):
    global telegram_app, http_session, streamlit_process

    if not TOKEN:
        raise RuntimeError("Missing TELEGRAM_BOT_TOKEN environment variable.")
    if not os.environ.get("OPENAI_API_KEY"):
        raise RuntimeError("Missing OPENAI_API_KEY environment variable.")
    if not BASE_URL:
        raise RuntimeError("Render did not provide RENDER_EXTERNAL_URL.")

    streamlit_file = find_streamlit_file()
    log.info("Starting Streamlit with %s", streamlit_file.name)

    # Start the Streamlit website on an internal port.
    streamlit_process = await asyncio.create_subprocess_exec(
        sys.executable, "-m", "streamlit", "run", str(streamlit_file),
        "--server.port", str(STREAMLIT_PORT),
        "--server.address", STREAMLIT_HOST,
        "--server.headless", "true",
        "--server.enableCORS", "false",
        "--server.enableXsrfProtection", "false",
        cwd=str(ROOT),
    )

    # Wait for Streamlit to become available.
    for _ in range(90):
        if streamlit_process.returncode is not None:
            raise RuntimeError("Streamlit exited during startup.")
        try:
            async with aiohttp.ClientSession() as test_session:
                async with test_session.get(
                    f"http://{STREAMLIT_HOST}:{STREAMLIT_PORT}/_stcore/health",
                    timeout=aiohttp.ClientTimeout(total=2),
                ) as response:
                    if response.status < 500:
                        break
        except Exception:
            pass
        await asyncio.sleep(1)
    else:
        raise RuntimeError("Streamlit did not become ready.")

    http_session = aiohttp.ClientSession(
        timeout=aiohttp.ClientTimeout(total=300)
    )

    telegram_app = Application.builder().token(TOKEN).build()
    telegram_app.add_handler(CommandHandler("start", start_command))
    telegram_app.add_handler(
        MessageHandler(
            (filters.TEXT & ~filters.COMMAND) | filters.PHOTO,
            handle_message,
        )
    )
    await telegram_app.initialize()
    await telegram_app.start()

    webhook_url = f"{BASE_URL}/telegram-webhook"
    await telegram_app.bot.set_webhook(
        url=webhook_url,
        secret_token=WEBHOOK_SECRET or None,
        allowed_updates=Update.ALL_TYPES,
        drop_pending_updates=False,
    )
    log.info("Telegram webhook configured: %s", webhook_url)


async def stop_background_services(app: web.Application):
    global telegram_app, http_session, streamlit_process

    if telegram_app is not None:
        try:
            # Do NOT delete the webhook here. When Render stops the service
            # (sleep or redeploy), Telegram must keep the webhook so the next
            # message can wake the service up again.
            await telegram_app.stop()
            await telegram_app.shutdown()
        except Exception:
            log.exception("Error stopping Telegram application")

    if http_session is not None:
        await http_session.close()

    if streamlit_process is not None and streamlit_process.returncode is None:
        streamlit_process.terminate()
        try:
            await asyncio.wait_for(streamlit_process.wait(), timeout=10)
        except asyncio.TimeoutError:
            streamlit_process.kill()
            await streamlit_process.wait()


def create_app():
    app = web.Application()
    app["webhook_secret"] = WEBHOOK_SECRET
    app.router.add_post("/telegram-webhook", telegram_webhook)
    app.router.add_get("/healthz", healthz)
    app.router.add_route("*", "/{tail:.*}", streamlit_proxy)
    app.on_startup.append(start_background_services)
    app.on_cleanup.append(stop_background_services)
    return app


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "10000"))
    web.run_app(create_app(), host="0.0.0.0", port=port)
