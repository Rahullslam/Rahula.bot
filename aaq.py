from __future__ import annotations

import asyncio
import base64
import io
import logging
import os
import random
import re
import string
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from dotenv import load_dotenv
from telegram import (
    KeyboardButton,
    ReplyKeyboardMarkup,
    Update,
)
from telegram.constants import ParseMode, ChatAction
from telegram.ext import (
    Application,
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

try:
    from playwright.async_api import async_playwright
except ImportError:
    async_playwright = None

# ANSI Color Codes for Terminal Console Output
YELLOW_COLOR = "\x1b[1;93m"
RESET_COLOR = "\x1b[0m"

# --------------------------------------------------------------------------- #
# Configuration
# --------------------------------------------------------------------------- #

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "8697229310:AAGegyamhKAIANZrDs_npoQ9-UdQbCFQTJg").strip()
ADMIN_ID_RAW = os.getenv("ADMIN_ID", "5233305923").strip()

BOT_USERNAME = "@htmlencrypt576_bot"
CHANNEL_USERNAME = "@rahul7zh"  
CHANNEL_LINK = "https://t.me/+v6HNF90XeDIyMmY9"  
OWNER_USERNAME = "@rahul_hackak"  
OWNER_NAME = "Rahul"

try:
    ADMIN_ID: Optional[int] = int(ADMIN_ID_RAW) if ADMIN_ID_RAW else None
except ValueError:
    ADMIN_ID = None

# Conversation States
WAITING_FOR_FILE = 1
WAITING_FOR_URL_TO_RAW_HTML = 2
WAITING_FOR_BROADCAST = 3

# UI Buttons
BTN_ENCODE = "🟡 🔐 ENCRYPT HTML FILE 🔐"
BTN_URL_TO_RAW_HTML = "🟡 🌐 URL to HTML (Original)"
BTN_ADMIN = "🟡 ⚙️ ADMIN PANEL"
BTN_BROADCAST = "📢 BROADCAST MESSAGE"
BTN_CANCEL = "❌ CANCEL OPERATION"

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger("html-encryptor-bot")

@dataclass
class BotState:
    bot_enabled: bool = True
    maintenance_mode: bool = False
    total_users: set = field(default_factory=set)
    total_encrypted: int = 0

STATE = BotState()

# --------------------------------------------------------------------------- #
# High Security Obfuscation Engine
# --------------------------------------------------------------------------- #

def generate_random_var(length: int = 10) -> str:
    first = random.choice(string.ascii_letters)
    rest = ''.join(random.choices(string.ascii_letters + string.digits, k=length - 1))
    return f"_{first}{rest}"

def encrypt_html_high_security(raw_html: str) -> str:
    key = ''.join(random.choices(string.ascii_letters + string.digits, k=32))
    
    xor_bytes = []
    for i, char in enumerate(raw_html):
        key_char = key[i % len(key)]
        xor_bytes.append(ord(char) ^ ord(key_char))
    
    encoded_stream = ",".join(map(str, xor_bytes))

    v_arr = generate_random_var()
    v_key = generate_random_var()
    v_out = generate_random_var()
    v_i = generate_random_var()
    v_b64 = generate_random_var()

    js_payload = f"""
    (function(){{
        var {v_arr} = [{encoded_stream}];
        var {v_key} = "{key}";
        var {v_out} = "";
        for (var {v_i} = 0; {v_i} < {v_arr}.length; {v_i}++) {{
            {v_out} += String.fromCharCode({v_arr}[{v_i}] ^ {v_key}.charCodeAt({v_i} % {v_key}.length));
        }}
        document.open();
        document.write({v_out});
        document.close();
    }})();
    """

    b64_payload = base64.b64encode(js_payload.encode('utf-8')).decode('utf-8')

    return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Protected Page</title>
</head>
<body>
<script type="text/javascript">
(function(){{
    var {v_b64} = "{b64_payload}";
    var _0xdata = atob({v_b64});
    var _0xelem = document.createElement('script');
    _0xelem.text = _0xdata;
    document.head.appendChild(_0xelem);
}})();
</script>
<noscript>JavaScript is required to view this protected page.</noscript>
</body>
</html>"""

def get_formatted_size(size_bytes: int) -> str:
    kb = size_bytes / 1024
    if kb >= 1024:
        return f"{kb / 1024:.1f} MB"
    return f"{kb:.1f} KB"

# --------------------------------------------------------------------------- #
# Web Fetching Engine
# --------------------------------------------------------------------------- #

async def fetch_html_from_url(url: str) -> Optional[bytes]:
    if async_playwright is not None:
        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(
                    headless=True,
                    args=['--no-sandbox', '--disable-setuid-sandbox', '--disable-dev-shm-usage']
                )
                context = await browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64)")
                page = await context.new_page()
                await page.goto(url, wait_until="networkidle", timeout=25000)
                content = await page.content()
                await browser.close()
                return content.encode("utf-8")
        except Exception as e:
            logger.warning(f"Playwright fetch failed: {e}")

    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'})
        with urllib.request.urlopen(req, timeout=15) as response:
            return response.read()
    except Exception as e:
        logger.error(f"Urllib fetch error: {e}")
        return None

# --------------------------------------------------------------------------- #
# Keyboards & Helpers
# --------------------------------------------------------------------------- #

def _is_admin(update: Update) -> bool:
    user = update.effective_user
    return bool(user and ADMIN_ID is not None and user.id == ADMIN_ID)

def main_menu_reply_keyboard(is_admin: bool) -> ReplyKeyboardMarkup:
    keyboard = [
        [KeyboardButton(BTN_ENCODE)],
        [KeyboardButton(BTN_URL_TO_RAW_HTML)]
    ]
    if is_admin:
        keyboard.append([KeyboardButton(BTN_ADMIN)])
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def admin_panel_reply_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup([
        [KeyboardButton(BTN_BROADCAST)],
        [KeyboardButton(BTN_CANCEL)]
    ], resize_keyboard=True)

def cancel_reply_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup([[KeyboardButton(BTN_CANCEL)]], resize_keyboard=True)

async def show_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    is_admin = _is_admin(update)
    text = (
        "🔐 <b>RAHUL HACK OBFUSCATOR BOT</b>\n\n"
        "Send an HTML file to encrypt or extract original source code from URL.\n\n"
        "👇 <b>Select an option below:</b>"
    )
    await update.effective_message.reply_text(
        text, parse_mode=ParseMode.HTML, reply_markup=main_menu_reply_keyboard(is_admin)
    )

# --------------------------------------------------------------------------- #
# Handlers
# --------------------------------------------------------------------------- #

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.effective_user:
        STATE.total_users.add(update.effective_user.id)
    await show_main_menu(update, context)
    return ConversationHandler.END

async def on_encode_button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.effective_message.reply_text(
        "📄 Please send your <b>.html</b> file to encrypt:",
        parse_mode=ParseMode.HTML,
        reply_markup=cancel_reply_keyboard()
    )
    return WAITING_FOR_FILE

async def on_url_to_raw_html_button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.effective_message.reply_text(
        "🌐 <b>URL to Original HTML Engine Active</b>\n\n"
        "Send the website URL to extract the <b>ORIGINAL (Unencrypted)</b> source code:\n"
        "Example: <code>https://example.com</code>",
        parse_mode=ParseMode.HTML,
        reply_markup=cancel_reply_keyboard()
    )
    return WAITING_FOR_URL_TO_RAW_HTML

async def on_admin_button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not _is_admin(update):
        await update.effective_message.reply_text("⛔ You are not authorized to view the admin panel.")
        return ConversationHandler.END

    stats_msg = (
        "⚙️ <b>ADMIN CONTROL PANEL</b>\n\n"
        f"👥 <b>Total Users:</b> <code>{len(STATE.total_users)}</code>\n"
        f"🔐 <b>Total Encrypted Files:</b> <code>{STATE.total_encrypted}</code>\n\n"
        "Choose an action below:"
    )
    await update.effective_message.reply_text(
        stats_msg, parse_mode=ParseMode.HTML, reply_markup=admin_panel_reply_keyboard()
    )
    return ConversationHandler.END

async def on_broadcast_button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not _is_admin(update):
        return ConversationHandler.END

    await update.effective_message.reply_text(
        "📢 <b>Broadcast Engine Active</b>\n\n"
        "Send the message, image, or link you want to broadcast to all bot users:",
        parse_mode=ParseMode.HTML,
        reply_markup=cancel_reply_keyboard()
    )
    return WAITING_FOR_BROADCAST

async def process_url_and_send(update: Update, context: ContextTypes.DEFAULT_TYPE, url: str):
    if update.effective_user:
        STATE.total_users.add(update.effective_user.id)

    if not url.startswith(("http://", "https://")):
        url = "https://" + url

    status_msg = await update.effective_message.reply_text(f"🌐 Fetching Original HTML from: {url} ...")
    await update.effective_message.chat.send_action(ChatAction.TYPING)

    try:
        raw_bytes = await fetch_html_from_url(url)
        if not raw_bytes:
            await status_msg.edit_text("❌ Failed to fetch HTML content from the link.")
            await show_main_menu(update, context)
            return

        filename = "rahul_extracted_file.html"
        original_size_str = get_formatted_size(len(raw_bytes))

        doc_file = io.BytesIO(raw_bytes)
        doc_file.name = filename

        caption = (
            f"📄 <b>Rahul Extracted File</b>\n\n"
            f"📊 Size: <b>{original_size_str}</b>\n\n"
            f"👑 Developer: {OWNER_USERNAME}\n"
            f"📢 Channel: {CHANNEL_LINK}"
        )

        await update.effective_message.reply_document(
            document=doc_file,
            filename=filename,
            caption=caption,
            parse_mode=ParseMode.HTML
        )
        
        await status_msg.delete()

    except Exception as e:
        logger.error(f"Error in URL to HTML conversion: {e}")
        await status_msg.edit_text(f"❌ Error occurred: {str(e)}")

    await show_main_menu(update, context)

async def handle_url_to_raw_html(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    url = update.effective_message.text.strip()
    await process_url_and_send(update, context, url)
    return ConversationHandler.END

async def process_document_and_send(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.effective_message
    document = message.document

    if not document or not document.file_name.endswith((".html", ".htm")):
        await message.reply_text("⚠️ Please upload a valid .html file.")
        return

    status_msg = await message.reply_text("⏳ Encrypting file...")

    try:
        tg_file = await document.get_file()
        file_bytes = await tg_file.download_as_bytearray()
        raw_text = file_bytes.decode("utf-8", errors="ignore")

        encrypted_html_str = encrypt_html_high_security(raw_text)
        encrypted_bytes = encrypted_html_str.encode('utf-8')

        original_size_str = get_formatted_size(len(file_bytes))
        encrypted_size_str = get_formatted_size(len(encrypted_bytes))

        out_filename = "rahul_encrypted_file.html"
        doc_file = io.BytesIO(encrypted_bytes)
        doc_file.name = out_filename

        caption = (
            f"🔐 <b>Rahul Encrypted File</b>\n\n"
            f"🛡️ Protection applied successfully.\n\n"
            f"📊 Size: <b>{original_size_str} → {encrypted_size_str}</b>\n\n"
            f"👑 Developer: {OWNER_USERNAME}\n"
            f"📢 Channel: {CHANNEL_LINK}"
        )

        await message.reply_document(
            document=doc_file,
            filename=out_filename,
            caption=caption,
            parse_mode=ParseMode.HTML
        )

        await status_msg.delete()
        STATE.total_encrypted += 1

    except Exception as exc:
        logger.error(f"Error: {exc}")
        await status_msg.edit_text(f"❌ Error occurred: {str(exc)}")

    await show_main_menu(update, context)

async def handle_html_document(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await process_document_and_send(update, context)
    return ConversationHandler.END

async def global_url_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = update.effective_message.text or ""
    urls = re.findall(r'https?://\S+', text)
    if urls:
        await process_url_and_send(update, context, urls[0])

async def global_document_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await process_document_and_send(update, context)

async def handle_broadcast_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not _is_admin(update):
        return ConversationHandler.END

    message = update.effective_message
    success_count = 0
    fail_count = 0

    status_msg = await message.reply_text("🚀 Broadcasting message to all users...")

    for user_id in list(STATE.total_users):
        try:
            if message.photo:
                photo_id = message.photo[-1].file_id
                caption = message.caption or ""
                await context.bot.send_photo(chat_id=user_id, photo=photo_id, caption=caption, parse_mode=ParseMode.HTML)
            elif message.text:
                await context.bot.send_message(chat_id=user_id, text=message.text, parse_mode=ParseMode.HTML, disable_web_page_preview=False)
            elif message.document:
                await context.bot.send_document(chat_id=user_id, document=message.document.file_id, caption=message.caption or "")
            success_count += 1
        except Exception as e:
            logger.error(f"Failed to send broadcast to {user_id}: {e}")
            fail_count += 1

    await status_msg.edit_text(
        f"✅ <b>Broadcast Completed!</b>\n\n"
        f"🎯 Successful: <code>{success_count}</code>\n"
        f"❌ Failed: <code>{fail_count}</code>",
        parse_mode=ParseMode.HTML
    )

    await show_main_menu(update, context)
    return ConversationHandler.END

async def cmd_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.effective_message.reply_text("Operation canceled.")
    await show_main_menu(update, context)
    return ConversationHandler.END

# --------------------------------------------------------------------------- #
# Application Wiring
# --------------------------------------------------------------------------- #

def build_application() -> Application:
    app = ApplicationBuilder().token(BOT_TOKEN).concurrent_updates(True).build()

    main_conv = ConversationHandler(
        entry_points=[
            MessageHandler(filters.Regex(f"^{re.escape(BTN_ENCODE)}$"), on_encode_button),
            MessageHandler(filters.Regex(f"^{re.escape(BTN_URL_TO_RAW_HTML)}$"), on_url_to_raw_html_button),
            MessageHandler(filters.Regex(f"^{re.escape(BTN_ADMIN)}$"), on_admin_button),
            MessageHandler(filters.Regex(f"^{re.escape(BTN_BROADCAST)}$"), on_broadcast_button),
        ],
        states={
            WAITING_FOR_FILE: [MessageHandler(filters.Document.ALL, handle_html_document)],
            WAITING_FOR_URL_TO_RAW_HTML: [MessageHandler(filters.TEXT & ~filters.COMMAND & ~filters.Regex(f"^{re.escape(BTN_CANCEL)}$"), handle_url_to_raw_html)],
            WAITING_FOR_BROADCAST: [MessageHandler(filters.ALL & ~filters.COMMAND & ~filters.Regex(f"^{re.escape(BTN_CANCEL)}$"), handle_broadcast_message)],
        },
        fallbacks=[
            CommandHandler("cancel", cmd_cancel),
            MessageHandler(filters.Regex(f"^{re.escape(BTN_CANCEL)}$"), cmd_cancel),
        ],
        per_user=True,
        per_chat=True,
    )

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(main_conv)
    
    # Global Handlers
    app.add_handler(MessageHandler(filters.Document.ALL, global_document_handler))
    app.add_handler(MessageHandler(filters.Entity("url") | filters.Regex(r"^https?://"), global_url_handler))

    return app

if __name__ == "__main__":
    print(f"{YELLOW_COLOR}║ BOT STARTED SUCCESSFULLY!{RESET_COLOR}")
    app = build_application()
    logger.info("Bot started...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)
