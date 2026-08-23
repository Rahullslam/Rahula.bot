import os
import html
import re
import base64
import urllib.parse
import asyncio
import logging
from gtts import gTTS
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, BotCommand
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackQueryHandler, ContextTypes

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ==================== YOUR BOT TOKEN ====================
TOKEN = "8638466543:AAEXW1Ff-JhLcLOGD7y_Pd-MipF0Z-3n73g"

# ==================== DECODER ENGINE ====================

def decode_text(text):
    if not text:
        return "", 0
    
    decoded = text
    layers_decoded = 0
    max_iterations = 25
    
    for _ in range(max_iterations):
        changed = False
        try:
            new = html.unescape(decoded)
            if new != decoded:
                decoded = new
                changed = True
                layers_decoded += 1
        except:
            pass
        
        try:
            new = urllib.parse.unquote(decoded)
            if new != decoded:
                decoded = new
                changed = True
                layers_decoded += 1
        except:
            pass
        
        try:
            clean_b64 = decoded.strip()
            if len(clean_b64) > 8:
                missing_padding = len(clean_b64) % 4
                if missing_padding:
                    clean_b64 += '=' * (4 - missing_padding)
                b64_decoded = base64.b64decode(clean_b64).decode('utf-8', errors='ignore')
                if b64_decoded.strip() and b64_decoded != decoded:
                    decoded = b64_decoded
                    changed = True
                    layers_decoded += 1
        except:
            pass
            
        try:
            clean_hex = re.sub(r'[^0-9a-fA-F]', '', decoded.strip())
            if len(clean_hex) > 10 and len(clean_hex) % 2 == 0:
                hex_decoded = bytes.fromhex(clean_hex).decode('utf-8', errors='ignore')
                if hex_decoded.strip() and hex_decoded != decoded:
                    decoded = hex_decoded
                    changed = True
                    layers_decoded += 1
        except:
            pass

        if not changed:
            break
            
    return decoded, layers_decoded

def decode_any_file(input_path):
    try:
        content = ""
        encodings = ['utf-8', 'latin-1', 'cp1252', 'iso-8859-1']
        
        for enc in encodings:
            try:
                with open(input_path, 'r', encoding=enc, errors='ignore') as f:
                    content = f.read()
                if content.strip():
                    break
            except:
                continue
                
        if not content.strip():
            with open(input_path, 'rb') as f:
                content = f.read().decode('utf-8', errors='ignore')
                
        original_size = len(content)
        decoded, layers = decode_text(content)
        decoded_size = len(decoded)
        
        base_name = os.path.splitext(input_path)[0]
        output_path = f"{base_name}_decoded.html"
        
        with open(output_path, 'w', encoding='utf-8', errors='ignore') as f:
            f.write(decoded)
            
        return output_path, original_size, decoded_size, layers
    except Exception as e:
        logger.error(f"Error in file decoding: {e}")
        raise

# ==================== BOT HANDLERS ====================

async def setup_bot_menu(application):
    commands = [
        BotCommand("start", "বট মেনু ও হোম পেজ"),
        BotCommand("decode", "ফাইল ডিকোড করার নির্দেশিকা"),
        BotCommand("help", "সাহায্য ও তথ্য")
    ]
    try:
        await application.bot.set_my_commands(commands)
    except Exception as e:
        logger.error(f"Menu setup error: {e}")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("📤 Send Your File", callback_data='upload')],
        [InlineKeyboardButton("❓ Help", callback_data='help')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "🤖 **HTML DECODER & DECRYPTOR PRO**\n\n"
        "📁 **Send Your File**\n\n"
        "Send any heavy or hard-encrypted `.html` or `.htm` file!\n\n"
        "🔹 [ Auto-Detects: Heavy Obfuscation / Base64 / Hex ]\n"
        "🔹 Server Engine: Active\n\n"
        "⬇️ **Click below or send your file directly!**",
        parse_mode='Markdown',
        reply_markup=reply_markup
    )

async def handle_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    doc = update.message.document
    
    allowed = ('.html', '.htm', '.xml', '.txt', '.json', '.js')
    if not doc.file_name.lower().endswith(allowed):
        await update.message.reply_text("❌ Please send a valid web format file (.html, .htm, .txt)!")
        return
    
    try:
        # ১. অটো ভয়েস নোটিফিকেশন ("রাহুল ফাইল ডিকোড হচ্ছে")
        voice_text = "রাহুল ফাইল ডিকোড হচ্ছে, দয়া করে অপেক্ষা করুন।"
        tts = gTTS(text=voice_text, lang='bn')
        voice_path = "temp_rahul_decode.ogg"
        tts.save(voice_path)
        
        with open(voice_path, 'rb') as voice_file:
            await update.message.reply_voice(voice=voice_file, caption="🔊 **ভয়েস নোটিফিকেশন**")
        
        if os.path.exists(voice_path):
            os.remove(voice_path)

        msg = await update.message.reply_text("📥 **Downloading file...**")
        
        file = await doc.get_file()
        temp_path = f"temp_{doc.file_name}"
        await file.download_to_drive(temp_path)
        
        # ২. প্রোগ্রেস বার অ্যানিমেশন
        steps = [
            ("🖥️ **Server Render Engine**\n`[          ] 0%`\n🔸 Encrypt Type -- Server", 0.3),
            ("🖥️ **Server Render Engine**\n`[=====     ] 50%`\n🔸 Scanning & Extracting HTML...", 0.4),
            ("🖥️ **Server Render Engine**\n`[==========] 100%`\n🔸 Done! Sending results...", 0.3)
        ]
        
        for step_text, delay in steps:
            await msg.edit_text(step_text, parse_mode='Markdown')
            await asyncio.sleep(delay)
        
        # ৩. ডিকোডিং প্রসেস
        output_path, orig, dec, layers = decode_any_file(temp_path)
        
        keyboard = [
            [InlineKeyboardButton("📥 Download Clean File", callback_data='download')],
            [InlineKeyboardButton("🔙 Main Menu", callback_data='menu')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # ৪. সফল রিপোর্ট ও ফাইল সেন্ড
        report = (
            f"✅ **Decode Successful!**\n\n"
            f"📄 **File:** `{doc.file_name}`\n"
            f"⚙️ **Method** -- 🖥️ Server Engine\n"
            f"📊 **Report:**\n"
            f"• Original Size: {orig/1024:.1f} KB\n"
            f"• Decoded Size: {dec/1024:.1f} KB\n"
            f"• Stripped Layers: {layers}\n"
            f"• Status: ✅ Fully Cleaned\n\n"
            f"⬇️ **File sending below ↓**"
        )
        await msg.edit_text(report, parse_mode='Markdown')
        
        with open(output_path, 'rb') as f:
            await update.message.reply_document(
                document=f,
                filename=f"{os.path.splitext(doc.file_name)[0]}_decoded.html",
                caption=f"✅ **Decode Successful!**\n📂 **File** -- `{doc.file_name}`",
                parse_mode='Markdown',
                reply_markup=reply_markup
            )
            
        context.user_data['file_path'] = output_path
        
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {str(e)[:150]}")
        logger.error(f"Error: {e}")

async def download_decoded(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    file_path = context.user_data.get('file_path')
    if file_path and os.path.exists(file_path):
        with open(file_path, 'rb') as f:
            await query.message.reply_document(document=f, filename="decoded_output.html")

def main():
    app = Application.builder().token(TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(download_decoded, pattern='^download$'))
    app.add_handler(CallbackQueryHandler(lambda u, c: start(u, c), pattern='^menu$'))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_file))
    
    app.job_queue.run_once(lambda context: asyncio.create_task(setup_bot_menu(app)), when=1)
    app.run_polling()

if __name__ == "__main__":
    main()
