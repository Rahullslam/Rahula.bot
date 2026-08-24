import os
import base64
import re
import time
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, CallbackQueryHandler, filters

# আপনার টেলিগ্রাম বটের টোকেন এখানে বসাবেন
TOKEN = "8959088769:AAHEjHMUTcw1TpOddFJXklssNfL6wLc7sTU"

async def handle_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    document = update.message.document
    if not document:
        await update.message.reply_text("📁 Please send an encrypted file (.html or .txt) to start decoding!")
        return

    unique_id = int(time.time())
    file = await context.bot.get_file(document.file_id)
    input_path = f"temp_{unique_id}_{document.file_name}"
    await file.download_to_drive(input_path)

    context.user_data['input_path'] = input_path
    context.user_data['file_name'] = document.file_name
    context.user_data['unique_id'] = unique_id

    keyboard = [
        [InlineKeyboardButton("⚡ Start AI Lock Decode", callback_data="ai_decode")],
        [InlineKeyboardButton("🛡️ Strip Security & Bypass", callback_data="bypass_security")],
        [InlineKeyboardButton("❌ Cancel", callback_data="cancel")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        "📥 File received successfully!\n\n"
        "Please select a decoding option below to proceed:",
        reply_markup=reply_markup
    )

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    data = query.data
    input_path = context.user_data.get('input_path')
    file_name = context.user_data.get('file_name', 'file.html')
    unique_id = context.user_data.get('unique_id', int(time.time()))

    if data == "cancel":
        await query.edit_message_text("❌ Operation cancelled.")
        if input_path and os.path.exists(input_path):
            os.remove(input_path)
        return

    if not input_path or not os.path.exists(input_path):
        await query.edit_message_text("⚠️ Session expired or file not found. Please send the file again.")
        return

    if data == "ai_decode":
        await query.edit_message_text("🤖 AI Lock Decoding in progress... Please wait.")
    elif data == "bypass_security":
        await query.edit_message_text("🛡️ Bypassing security locks & clearing restrictions...")

    try:
        with open(input_path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()

        content = re.sub(r'<div[^>]*>[\s\S]*?(?:SECURITY STATUS|RESTRICTED|DEPRECATED|HTMLObfuscateBot)[\s\S]*?<\/div>', '', content, flags=re.IGNORECASE)
        
        for _ in range(3):
            b64_match = re.search(r'atob\(['"]([A-Za-z0-9+/=]+)['"]\)', content) or re.search(r'["\']([A-Za-z0-9+/=]{100,})["\']', content)
            if b64_match:
                try:
                    unsealed = base64.b64decode(b64_match.group(1)).decode('utf-8')
                    if len(unsealed) > len(content) / 2 or '<html' in unsealed.lower():
                        content = unsealed
                except:
                    break
            else:
                break

        output_filename = f"decoded_{unique_id}_{file_name}"
        with open(output_filename, "w", encoding="utf-8") as f:
            f.write(content)

        await context.bot.send_message(
            chat_id=query.message.chat_id,
            text="✅ Success! AI successfully decoded and unlocked the file."
        )

        await context.bot.send_document(
            chat_id=query.message.chat_id,
            document=open(output_filename, "rb"),
            caption="📂 Here is your freshly decoded and cleaned file!"
        )

        if os.path.exists(output_filename):
            os.remove(output_filename)

    except Exception as e:
        await context.bot.send_message(
            chat_id=query.message.chat_id,
            text=f"❌ Decoding Error: {str(e)}"
        )
        
    finally:
        if os.path.exists(input_path):
            os.remove(input_path)

if __name__ == '__main__':
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(MessageHandler(filters.Document.ALL, handle_file))
    app.add_handler(CallbackQueryHandler(button_handler))
    print("🤖 Bot is running smoothly...")
    app.run_polling()
