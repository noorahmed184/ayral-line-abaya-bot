# -*- coding: utf-8 -*-

import os
import asyncio
import logging

from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters
)

from bot_core import AbayaBot
from notifications import notify_staff


# ───────────────────────── Logging ─────────────────────────

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)

logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)


# ───────────────────────── Environment ─────────────────────────

TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()

ERROR_MSG = "عذراً، صار خطأ. حاولي مرة ثانية 🌸"

# Separate conversation for each Telegram chat
bots = {}


# ───────────────────────── Get bot ─────────────────────────

def get_bot(chat_id):

    if chat_id not in bots:
        bots[chat_id] = AbayaBot()

    return bots[chat_id]


# ───────────────────────── Start command ─────────────────────────

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):

    chat_id = update.effective_chat.id

    bots.pop(chat_id, None)

    await update.effective_message.reply_text(
        "هلا فيج في أيرال لاين 🌸\n"
        "شلون أقدر أساعدج؟"
    )


# ───────────────────────── Handle messages ─────────────────────────

async def handle(update: Update, context: ContextTypes.DEFAULT_TYPE):

    msg = update.effective_message
    chat_id = update.effective_chat.id

    text = (msg.text or msg.caption or "").strip()

    image_bytes = None

    # Download customer image
    if msg.photo:

        photo = await msg.photo[-1].get_file()

        image_bytes = bytes(
            await photo.download_as_bytearray()
        )

    if not text and not image_bytes:
        return

    await context.bot.send_chat_action(
        chat_id=chat_id,
        action=ChatAction.TYPING
    )

    try:

        bot = await asyncio.to_thread(
            get_bot,
            chat_id
        )

        answer, handoff = await asyncio.to_thread(
            bot.reply,
            text,
            image_bytes
        )

    except Exception:

        logging.exception("Bot reply error")

        await msg.reply_text(ERROR_MSG)

        return

    await msg.reply_text(
        answer or "حاولي مرة ثانية 🌸"
    )

    # Notify staff if conversation needs handoff
    if handoff:

        user = update.effective_user

        username = user.username or "No username"

        who = (
            f"تلقرام: {user.full_name} "
            f"(@{username}) id={user.id}"
        )

        try:

            await asyncio.to_thread(
                notify_staff,
                who,
                handoff,
                text or "(صورة)"
            )

            await msg.reply_text(
                f"🔔 تم تحويل المحادثة للموظفة: {handoff}"
            )

        except Exception:

            logging.exception("Staff notification error")


# ───────────────────────── Main ─────────────────────────

def main():

    if not TOKEN:
        raise ValueError(
            "TELEGRAM_BOT_TOKEN is missing!"
        )

    application = (
        ApplicationBuilder()
        .token(TOKEN)
        .build()
    )

    application.add_handler(
        CommandHandler("start", start)
    )

    application.add_handler(
        MessageHandler(
            (filters.TEXT & ~filters.COMMAND) | filters.PHOTO,
            handle
        )
    )

    logging.info("AERAL LINE Telegram Bot is starting with Polling...")

    application.run_polling(
        drop_pending_updates=False
    )


if __name__ == "__main__":
    main()
