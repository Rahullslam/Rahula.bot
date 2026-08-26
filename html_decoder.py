import os
import logging
import re
from datetime import datetime
from collections import Counter
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
import io

# ==================== CONFIGURATION ====================
BOT_TOKEN = "8905282088:AAF5Py6J4vl_k4Jp7q6QAr2Qh-NqxLZM6aA"

# ==================== LOGGING ====================
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ==================== HTML DECODER ====================
class HTMLDecoder:
    def __init__(self, html_content, filename="unknown.html"):
        self.html_content = html_content
        self.filename = filename
        self.stats = {}
        self.errors = []
        self.warnings = []
        
    def decode(self):
        try:
            self.stats['total_chars'] = len(self.html_content)
            self.stats['total_lines'] = self.html_content.count('\n') + 1
            self.stats['total_words'] = len(re.findall(r'\w+', self.html_content))
            self._analyze_html()
            
            return {
                'status': 'success',
                'stats': self.stats,
                'errors': self.errors,
                'warnings': self.warnings
            }
        except Exception as e:
            self.errors.append(str(e))
            return {
                'status': 'error',
                'error': str(e),
                'stats': self.stats,
                'errors': self.errors
            }
    
    def _analyze_html(self):
        content = self.html_content
        
        # Tags
        tag_pattern = r'<([a-zA-Z][a-zA-Z0-9]*)[^>]*>'
        tags = re.findall(tag_pattern, content)
        self.stats['tags'] = dict(Counter(tags))
        self.stats['total_tags'] = len(tags)
        self.stats['unique_tags'] = len(self.stats['tags'])
        
        # Links
        link_pattern = r'<a[^>]*href=[\'"]([^\'"]*)[\'"][^>]*>'
        links = re.findall(link_pattern, content, re.IGNORECASE)
        self.stats['links'] = links[:10]
        self.stats['total_links'] = len(links)
        
        # Images
        img_pattern = r'<img[^>]*src=[\'"]([^\'"]*)[\'"][^>]*>'
        images = re.findall(img_pattern, content, re.IGNORECASE)
        self.stats['images'] = images[:10]
        self.stats['total_images'] = len(images)
        
        # Scripts
        script_pattern = r'<script[^>]*>.*?</script>'
        scripts = re.findall(script_pattern, content, re.IGNORECASE | re.DOTALL)
        self.stats['total_scripts'] = len(scripts)
        
        # Styles
        style_pattern = r'<style[^>]*>.*?</style>'
        styles = re.findall(style_pattern, content, re.IGNORECASE | re.DOTALL)
        self.stats['total_styles'] = len(styles)
        
        # Forms
        form_pattern = r'<form[^>]*>'
        forms = re.findall(form_pattern, content, re.IGNORECASE)
        self.stats['total_forms'] = len(forms)
        
        # Headings
        headings = {}
        for i in range(1, 7):
            h_pattern = rf'<h{i}[^>]*>(.*?)</h{i}>'
            h_content = re.findall(h_pattern, content, re.IGNORECASE | re.DOTALL)
            if h_content:
                headings[f'h{i}'] = [h[:40].strip() for h in h_content[:5]]
        self.stats['headings'] = headings
        
        # Paragraphs
        p_pattern = r'<p[^>]*>(.*?)</p>'
        paragraphs = re.findall(p_pattern, content, re.IGNORECASE | re.DOTALL)
        self.stats['total_paragraphs'] = len(paragraphs)
        
        # Tables
        table_pattern = r'<table[^>]*>'
        tables = re.findall(table_pattern, content, re.IGNORECASE)
        self.stats['total_tables'] = len(tables)
        
        # Comments
        comment_pattern = r'<!--(.*?)-->'
        comments = re.findall(comment_pattern, content, re.DOTALL)
        self.stats['total_comments'] = len(comments)
        
        # Title
        title_pattern = r'<title[^>]*>(.*?)</title>'
        title_match = re.search(title_pattern, content, re.IGNORECASE | re.DOTALL)
        self.stats['title'] = title_match.group(1).strip() if title_match else 'No title found'
        
        # Meta description
        meta_pattern = r'<meta[^>]*name=[\'"]description[\'"][^>]*content=[\'"]([^\'"]*)[\'"][^>]*>'
        meta_match = re.search(meta_pattern, content, re.IGNORECASE)
        self.stats['meta_description'] = meta_match.group(1) if meta_match else 'No description'
        
        # Encoding
        encoding_pattern = r'<meta[^>]*charset=[\'"]([^\'"]*)[\'"][^>]*>'
        encoding_match = re.search(encoding_pattern, content, re.IGNORECASE)
        self.stats['encoding'] = encoding_match.group(1) if encoding_match else 'UTF-8 (default)'
        
        # Clean text
        text_content = re.sub(r'<[^>]+>', ' ', content)
        text_content = re.sub(r'\s+', ' ', text_content)
        self.stats['clean_text'] = text_content[:300]
        self.stats['file_size_kb'] = len(self.html_content) / 1024

# ==================== BOT HANDLERS ====================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("📄 Upload HTML", callback_data='upload')],
        [InlineKeyboardButton("📝 Paste HTML", callback_data='paste')],
        [InlineKeyboardButton("🛠️ Support / Help", callback_data='support')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "🤖 *HTML Decoder Bot*\n\n"
        "Send any HTML file or paste your code.\n"
        "I will decode and analyze it for you!\n\n"
        "📌 *Choose an option below:*",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data == 'upload':
        await query.edit_message_text(
            "📄 *Upload HTML File*\n\n"
            "Please send your `.html`, `.htm`, or `.txt` file.\n"
            "Maximum file size: 10 MB",
            parse_mode='Markdown'
        )
        context.user_data['mode'] = 'waiting_file'
        
    elif query.data == 'paste':
        await query.edit_message_text(
            "📝 *Paste HTML Code*\n\n"
            "Just paste your HTML code directly into the chat.",
            parse_mode='Markdown'
        )
        context.user_data['mode'] = 'waiting_html'
        
    elif query.data == 'support':
        keyboard = [[InlineKeyboardButton("🔙 Back to Menu", callback_data='back_home')]]
        await query.edit_message_text(
            "🛠️ *Support & Help Center*\n\n"
            "• You can upload HTML files or paste code directly.\n"
            "• The bot extracts tags, links, images, titles, and metadata.\n"
            "• Max file size allowed is 10 MB.\n\n"
            "If you face any issues, contact the developer.",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
        
    elif query.data == 'back_home':
        keyboard = [
            [InlineKeyboardButton("📄 Upload HTML", callback_data='upload')],
            [InlineKeyboardButton("📝 Paste HTML", callback_data='paste')],
            [InlineKeyboardButton("🛠️ Support / Help", callback_data='support')]
        ]
        await query.edit_message_text(
            "🤖 *HTML Decoder Bot*\n\n"
            "Send any HTML file or paste your code.\n"
            "I will decode and analyze it for you!\n\n"
            "📌 *Choose an option below:*",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )

async def handle_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get('mode') != 'waiting_file':
        await update.message.reply_text("⚠️ Please click 'Upload HTML' from the menu first!")
        return
    
    document = update.message.document
    
    if not document.file_name.endswith(('.html', '.htm', '.txt')):
        await update.message.reply_text("❌ Only .html, .htm, and .txt files are supported!")
        return
    
    if document.file_size > 10 * 1024 * 1024:
        await update.message.reply_text("❌ Maximum file size is 10 MB!")
        return
    
    processing_msg = await update.message.reply_text("⏳ Processing your file...")
    
    try:
        file = await context.bot.get_file(document.file_id)
        file_content = await file.download_as_bytearray()
        html_content = file_content.decode('utf-8', errors='ignore')
        
        decoder = HTMLDecoder(html_content, document.file_name)
        result = decoder.decode()
        
        await processing_msg.delete()
        await show_result(update, context, result)
        
    except Exception as e:
        await processing_msg.edit_text(f"❌ Error: {str(e)[:100]}")
        logger.error(f"File error: {e}")

async def handle_html_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get('mode') != 'waiting_html':
        await update.message.reply_text("⚠️ Please click 'Paste HTML' from the menu first!")
        return
    
    html_content = update.message.text
    
    if len(html_content) > 100000:
        await update.message.reply_text("⚠️ Code is too long! Please upload it as a file instead.")
        return
    
    processing_msg = await update.message.reply_text("⏳ Decoding HTML code...")
    
    try:
        decoder = HTMLDecoder(html_content, "pasted.html")
        result = decoder.decode()
        
        await processing_msg.delete()
        await show_result(update, context, result)
        
    except Exception as e:
        await processing_msg.edit_text(f"❌ Error: {str(e)[:100]}")
        logger.error(f"Text error: {e}")

async def show_result(update: Update, context: ContextTypes.DEFAULT_TYPE, result):
    if result['status'] == 'error':
        await update.message.reply_text(
            f"❌ *Decoding Error*\n\n```\n{result.get('error', 'Unknown')}\n```",
            parse_mode='Markdown'
        )
        return
    
    stats = result['stats']
    doc = getattr(update.message, 'document', None)
    filename = doc.file_name if doc else "pasted.html"
    
    message = "✅ *HTML Decoding Complete!*\n\n"
    message += f"📄 *File:* `{filename}`\n"
    message += f"📊 *Size:* {stats['file_size_kb']:.2f} KB\n"
    message += f"📝 *Chars:* {stats['total_chars']:,}\n"
    message += f"📝 *Words:* {stats['total_words']:,}\n\n"
    
    message += f"📌 *Title:* {stats['title'][:60]}\n"
    if stats['meta_description'] != 'No description':
        message += f"📝 *Meta:* {stats['meta_description'][:80]}\n"
    message += f"🔤 *Encoding:* {stats['encoding']}\n\n"
    
    message += f"🏷️ *Tags:* {stats['total_tags']:,} total, {stats['unique_tags']} unique\n"
    message += "*Top tags:*\n"
    for tag, count in sorted(stats['tags'].items(), key=lambda x: x[1], reverse=True)[:6]:
        message += f"  • `<{tag}>`: {count}\n"
    message += "\n"
    
    message += f"🔗 *Links:* {stats['total_links']}\n"
    message += f"🖼️ *Images:* {stats['total_images']}\n"
    message += f"📝 *Paragraphs:* {stats['total_paragraphs']}\n"
    message += f"📊 *Tables:* {stats['total_tables']}\n"
    message += f"📋 *Forms:* {stats['total_forms']}\n"
    message += f"💬 *Comments:* {stats['total_comments']}\n"
    
    await update.message.reply_text(
        message,
        parse_mode='Markdown',
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔄 Decode Another", callback_data='upload')]
        ])
    )

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.error(f"Update {update} error: {context.error}")

import asyncio

# ==================== MAIN ====================
async def main_async():
    if BOT_TOKEN == "8905282088:AAF5Py6J4vl_k4Jp7q6QAr2Qh-NqxLZM6aA":
        print("❌ ERROR: Please set your BOT_TOKEN!")
        return
    
    try:
        application = Application.builder().token(BOT_TOKEN).build()
        
        application.add_handler(CommandHandler("start", start))
        application.add_handler(CallbackQueryHandler(button_handler))
        application.add_handler(MessageHandler(filters.Document.ALL, handle_file))
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_html_text))
        application.add_error_handler(error_handler)
        
        print("\n" + "="*50)
        print("🤖 HTML DECODER BOT STARTED SUCCESSFULLY")
        print("="*50)
        
        # Proper initialization and running for Render / Production
        await application.initialize()
        await application.start()
        await application.updater.start_polling(allowed_updates=Update.ALL_TYPES)
        
        # Keep the bot running
        stop_event = asyncio.Event()
        await stop_event.wait()
        
    except Exception as e:
        print(f"\n❌ Failed to start: {e}")

def main():
    try:
        asyncio.run(main_async())
    except (KeyboardInterrupt, SystemExit):
        pass

if __name__ == "__main__":
    main()
