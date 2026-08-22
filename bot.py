import os
import re
import html
import gzip
import zlib
import base64
import chardet
import binascii
import requests
import urllib.parse
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackQueryHandler, ContextTypes
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TOKEN = "8783710941:AAEtfegwlNfe50KGC1bSEYo96cLEvhF4f5Y"

# ==================== থাম্বনেইন জেনারেটর ====================

class ThumbnailGenerator:
    @staticmethod
    def generate_thumbnail(file_path, file_name, file_size):
        try:
            width, height = 400, 300
            img = Image.new('RGB', (width, height), color='#0a0a1a')
            draw = ImageDraw.Draw(img)
            
            for i in range(height):
                color = int(20 + (i * 0.1))
                draw.rectangle([0, i, width, i+1], fill=(color, color, 40))
            
            draw.rectangle([5, 5, width-5, height-5], outline='#00ff88', width=2)
            
            ext = os.path.splitext(file_name)[1].lower()
            icons = {
                '.html': '🌐', '.htm': '🌐', '.xml': '📋', '.json': '📊',
                '.txt': '📝', '.log': '📜', '.csv': '📈', '.py': '🐍',
                '.js': '🟨', '.css': '🎨', '.cpp': '⚡', '.java': '☕'
            }
            icon = icons.get(ext, '📄')
            
            try:
                font = ImageFont.truetype("/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf", 80)
                small_font = ImageFont.truetype("/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf", 24)
            except:
                font = ImageFont.load_default()
                small_font = ImageFont.load_default()
            
            draw.text((width//2 - 40, height//2 - 70), icon, fill='#00ff88', font=font)
            name = file_name[:18] + '...' if len(file_name) > 18 else file_name
            draw.text((width//2 - 80, height//2 + 20), name, fill='white', font=small_font)
            size_text = f"{file_size / 1024:.1f} KB" if file_size < 1024*1024 else f"{file_size / (1024*1024):.1f} MB"
            draw.text((width//2 - 50, height//2 + 50), size_text, fill='#8888ff', font=small_font)
            
            thumb_path = f"thumb_{file_name}.png"
            img.save(thumb_path)
            return thumb_path
        except Exception as e:
            logger.error(f"Thumbnail error: {e}")
            return None

# ==================== আলটিমেট ডিকোডার ====================

class UltimateDecoder:
    @staticmethod
    def detect_encoding(content):
        if isinstance(content, str):
            content = content.encode('utf-8', errors='ignore')
        result = chardet.detect(content[:50000])
        return result['encoding'] or 'utf-8'
    
    @staticmethod
    def is_hex(data):
        try:
            if len(data) > 10 and all(c in '0123456789ABCDEFabcdef \n\r\t' for c in data[:100]):
                return True
        except:
            pass
        return False
    
    @staticmethod
    def decode_hex(hex_str):
        try:
            clean = re.sub(r'[^0-9a-fA-F]', '', hex_str)
            if len(clean) % 2 == 0:
                return bytes.fromhex(clean).decode('utf-8', errors='ignore')
        except:
            pass
        return hex_str
    
    @staticmethod
    def is_base64(data):
        try:
            clean = data.strip()
            if len(clean) > 10:
                pattern = re.compile(r'^[A-Za-z0-9+/]+=*$')
                if pattern.match(clean[:100]):
                    return True
        except:
            pass
        return False
    
    @staticmethod
    def decode_base64(data):
        try:
            clean = data.strip()
            while len(clean) % 4 != 0:
                clean += '='
            decoded = base64.b64decode(clean)
            return decoded.decode('utf-8', errors='ignore')
        except:
            return data
    
    @staticmethod
    def is_rot13(data):
        try:
            if len(data) > 10:
                decoded = data.translate(str.maketrans(
                    'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz',
                    'NOPQRSTUVWXYZABCDEFGHIJKLMNOPQRSTUVWXYZABCDEFGHIJKLM'
                ))
                if decoded != data:
                    return True
        except:
            pass
        return False
    
    @staticmethod
    def decode_rot13(data):
        return data.translate(str.maketrans(
            'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz',
            'NOPQRSTUVWXYZABCDEFGHIJKLMNOPQRSTUVWXYZABCDEFGHIJKLM'
        ))
    
    @staticmethod
    def is_url_encoded(data):
        try:
            if '%' in data:
                decoded = urllib.parse.unquote(data)
                if decoded != data:
                    return True
        except:
            pass
        return False
    
    @staticmethod
    def decode_content(text):
        max_iterations = 20
        decoded = text
        history = []
        changed_count = 0
        
        for iteration in range(max_iterations):
            changed = False
            original = decoded
            
            try:
                new_text = html.unescape(decoded)
                if new_text != decoded:
                    decoded = new_text
                    changed = True
                    changed_count += 1
            except:
                pass
            
            if UltimateDecoder.is_url_encoded(decoded):
                try:
                    new_text = urllib.parse.unquote(decoded)
                    if new_text != decoded:
                        decoded = new_text
                        changed = True
                        changed_count += 1
                except:
                    pass
            
            if UltimateDecoder.is_base64(decoded):
                try:
                    new_text = UltimateDecoder.decode_base64(decoded)
                    if new_text != decoded and len(new_text) > 0:
                        decoded = new_text
                        changed = True
                        changed_count += 1
                except:
                    pass
            
            if UltimateDecoder.is_hex(decoded):
                try:
                    new_text = UltimateDecoder.decode_hex(decoded)
                    if new_text != decoded and len(new_text) > 0:
                        decoded = new_text
                        changed = True
                        changed_count += 1
                except:
                    pass
            
            if UltimateDecoder.is_rot13(decoded):
                try:
                    new_text = UltimateDecoder.decode_rot13(decoded)
                    if new_text != decoded:
                        decoded = new_text
                        changed = True
                        changed_count += 1
                except:
                    pass
            
            try:
                new_text = decoded.encode('utf-8').decode('unicode_escape')
                if new_text != decoded:
                    decoded = new_text
                    changed = True
                    changed_count += 1
            except:
                pass
            
            preview = decoded[:200]
            if preview in history:
                break
            history.append(preview)
            
            if not changed:
                break
        
        logger.info(f"Decoded {changed_count} layers")
        return decoded
    
    @staticmethod
    def decode_file(input_path):
        try:
            logger.info(f"Decoding file: {input_path}")
            
            with open(input_path, 'rb') as f:
                raw_data = f.read()
            
            if raw_data[:2] == b'\x1f\x8b':
                try:
                    raw_data = gzip.decompress(raw_data)
                    logger.info("GZIP decompressed")
                except:
                    pass
            
            try:
                raw_data = zlib.decompress(raw_data)
                logger.info("ZLIB decompressed")
            except:
                pass
            
            encoding = UltimateDecoder.detect_encoding(raw_data)
            logger.info(f"Detected encoding: {encoding}")
            
            try:
                text = raw_data.decode(encoding, errors='ignore')
            except:
                text = raw_data.decode('utf-8', errors='ignore')
            
            logger.info("Starting multi-layer decoding...")
            decoded_text = UltimateDecoder.decode_content(text)
            
            output_path = input_path + "_DECODED_FINAL"
            with open(output_path, 'w', encoding='utf-8', errors='ignore') as f:
                f.write(decoded_text)
            
            logger.info(f"Decoding complete. Output: {output_path}")
            return output_path, len(text), len(decoded_text)
            
        except Exception as e:
            logger.error(f"Decode error: {e}")
            raise

# ==================== বট হ্যান্ডলার ====================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """স্টার্ট কমান্ড - সব অপশন বটের নিচে"""
    
    # মেইন মেনু বাটন
    keyboard = [
        [InlineKeyboardButton("📤 ফাইল আপলোড করুন", callback_data='upload_file')],
        [InlineKeyboardButton("🔗 লিংক থেকে ডিকোড করুন", callback_data='decode_link')],
        [InlineKeyboardButton("🖼️ ইমেজ দেখান", callback_data='show_image')],
        [InlineKeyboardButton("📋 XML ডিকোড", callback_data='decode_xml')],
        [InlineKeyboardButton("🌐 HTML ডিকোড", callback_data='decode_html')],
        [InlineKeyboardButton("🗑️ ফাইল ডিলিট করুন", callback_data='delete_files')],
        [InlineKeyboardButton("❓ সাহায্য", callback_data='help_menu')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "🔥 **ডিকোডার বট v5.0**\n\n"
        "📌 **নিচের অপশন থেকে চয়ন করুন:**\n\n"
        "✅ **ফিচারসমূহ:**\n"
        "• HTML Entities ডিকোড\n"
        "• URL Encode ডিকোড\n"
        "• Base64 ডিকোড\n"
        "• Hex ডিকোড\n"
        "• ROT13 ডিকোড\n"
        "• GZIP/ZLIB আনজিপ\n"
        "• মাল্টি-লেয়ার ডিকোড\n\n"
        "🛡️ **সব সিকিউরিটি ব্রেক করবো!**",
        parse_mode='Markdown',
        reply_markup=reply_markup
    )

async def main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """মেইন মেনু দেখান"""
    query = update.callback_query
    await query.answer()
    
    keyboard = [
        [InlineKeyboardButton("📤 ফাইল আপলোড করুন", callback_data='upload_file')],
        [InlineKeyboardButton("🔗 লিংক থেকে ডিকোড করুন", callback_data='decode_link')],
        [InlineKeyboardButton("🖼️ ইমেজ দেখান", callback_data='show_image')],
        [InlineKeyboardButton("📋 XML ডিকোড", callback_data='decode_xml')],
        [InlineKeyboardButton("🌐 HTML ডিকোড", callback_data='decode_html')],
        [InlineKeyboardButton("🗑️ ফাইল ডিলিট করুন", callback_data='delete_files')],
        [InlineKeyboardButton("❓ সাহায্য", callback_data='help_menu')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        "🏠 **মেইন মেনু**\n\n"
        "নিচের অপশন থেকে চয়ন করুন:\n\n"
        "📤 ফাইল আপলোড করুন - XML/HTML ফাইল পাঠান\n"
        "🔗 লিংক থেকে ডিকোড করুন - URL থেকে HTML ডাউনলোড\n"
        "🖼️ ইমেজ দেখান - আপনার পিক দেখাবো\n"
        "📋 XML ডিকোড - XML ফাইল ডিকোড\n"
        "🌐 HTML ডিকোড - HTML ফাইল ডিকোড\n"
        "🗑️ ফাইল ডিলিট করুন - টেম্প ফাইল ডিলিট",
        parse_mode='Markdown',
        reply_markup=reply_markup
    )

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """বাটন কলব্যাক হ্যান্ডলার"""
    query = update.callback_query
    await query.answer()
    
    if query.data == 'upload_file':
        await query.edit_message_text(
            "📤 **ফাইল আপলোড করুন**\n\n"
            "HTML, XML, TXT, JSON যেকোনো ফাইল পাঠান।\n"
            "আমি অটো ডিকোড করে দেবো!\n\n"
            "📌 ফাইল পাঠানোর জন্য নিচের বাটনে ক্লিক করুন:\n"
            "➡️ **Attach** বাটনে ক্লিক করে ফাইল নির্বাচন করুন।",
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 মেনুতে ফিরুন", callback_data='main_menu')]
            ])
        )
    
    elif query.data == 'decode_link':
        await query.edit_message_text(
            "🔗 **লিংক থেকে ডিকোড**\n\n"
            "যে ওয়েবসাইট থেকে HTML ডাউনলোড করতে চান তার লিংক দিন।\n\n"
            "📌 **উদাহরণ:**\n"
            "`https://example.com/encoded.html`\n\n"
            "লিংকটি টাইপ করে পাঠান।",
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 মেনুতে ফিরুন", callback_data='main_menu')]
            ])
        )
    
    elif query.data == 'show_image':
        await query.edit_message_text(
            "🖼️ **ইমেজ দেখান**\n\n"
            "আপনি যে পিক দেখাতে চান তা পাঠান।\n"
            "JPG, PNG, GIF সব সাপোর্ট করে।\n\n"
            "📌 **ইমেজ পাঠানোর নিয়ম:**\n"
            "➡️ **Attach** বাটনে ক্লিক করে ইমেজ নির্বাচন করুন।",
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 মেনুতে ফিরুন", callback_data='main_menu')]
            ])
        )
    
    elif query.data == 'decode_xml':
        await query.edit_message_text(
            "📋 **XML ডিকোড**\n\n"
            "XML ফাইল ডিকোড করতে:\n"
            "1️⃣ XML ফাইল পাঠান\n"
            "2️⃣ আমি ডিকোড করবো\n"
            "3️⃣ ডিকোডেড ফাইল পাবেন\n\n"
            "📌 ফাইল পাঠানোর জন্য **Attach** বাটনে ক্লিক করুন।",
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 মেনুতে ফিরুন", callback_data='main_menu')]
            ])
        )
    
    elif query.data == 'decode_html':
        await query.edit_message_text(
            "🌐 **HTML ডিকোড**\n\n"
            "HTML ফাইল ডিকোড করতে:\n"
            "1️⃣ HTML ফাইল পাঠান\n"
            "2️⃣ আমি ডিকোড করবো\n"
            "3️⃣ ডিকোডেড ফাইল পাবেন\n\n"
            "📌 ফাইল পাঠানোর জন্য **Attach** বাটনে ক্লিক করুন।",
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 মেনুতে ফিরুন", callback_data='main_menu')]
            ])
        )
    
    elif query.data == 'delete_files':
        await delete_all_files(update, context)
    
    elif query.data == 'help_menu':
        await query.edit_message_text(
            "❓ **সাহায্য**\n\n"
            "📌 **কীভাবে ব্যবহার করবেন:**\n\n"
            "1️⃣ **ফাইল আপলোড:**\n"
            "   XML/HTML ফাইল পাঠান\n\n"
            "2️⃣ **লিংক থেকে ডিকোড:**\n"
            "   ওয়েবপেজের URL দিন\n\n"
            "3️⃣ **ইমেজ দেখান:**\n"
            "   আপনার পিক পাঠান\n\n"
            "4️⃣ **XML/HTML ডিকোড:**\n"
            "   নির্দিষ্ট ফাইল ডিকোড করুন\n\n"
            "5️⃣ **ফাইল ডিলিট:**\n"
            "   টেম্প ফাইল ক্লিন করুন\n\n"
            "🛡️ **সাপোর্টেড এনকোডিং:**\n"
            "• HTML Entities (`&amp;`)\n"
            "• URL Encode (`%20`)\n"
            "• Base64 (এনক্রিপ্টেড)\n"
            "• Hex (হেক্সাডেসিমেল)\n"
            "• ROT13 (সিজার সাইফার)\n"
            "• GZIP/ZLIB কম্প্রেশন\n"
            "• মাল্টি-লেয়ার (২০ লেয়ার)",
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 মেনুতে ফিরুন", callback_data='main_menu')]
            ])
        )
    
    elif query.data == 'main_menu':
        await main_menu(update, context)

async def delete_all_files(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """সব ফাইল ডিলিট"""
    query = update.callback_query
    await query.answer()
    
    deleted = []
    
    # টেম্প ফাইল চেক
    for file in os.listdir('.'):
        if file.startswith('temp_') or file.startswith('thumb_') or file.endswith('_DECODED_FINAL'):
            try:
                os.remove(file)
                deleted.append(file)
            except:
                pass
    
    # ক্লিন আপ
    context.user_data.clear()
    
    if deleted:
        await query.edit_message_text(
            f"🗑️ **{len(deleted)} টি ফাইল ডিলিট করা হয়েছে!**\n\n"
            f"📌 ডিলিট করা ফাইল:\n"
            f"```\n{chr(10).join(deleted[:10])}\n```\n"
            f"{'... এবং আরও' if len(deleted) > 10 else ''}\n\n"
            f"✅ সব টেম্প ডেটা ক্লিন করা হয়েছে।",
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 মেনুতে ফিরুন", callback_data='main_menu')]
            ])
        )
    else:
        await query.edit_message_text(
            "✅ **কোনো ফাইল ডিলিট করার নেই!**\n\n"
            "সব টেম্প ফাইল ইতিমধ্যে ক্লিন করা হয়েছে।",
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 মেনুতে ফিরুন", callback_data='main_menu')]
            ])
        )

async def handle_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """লিংক থেকে ডিকোড"""
    url = update.message.text.strip()
    
    if not url.startswith(('http://', 'https://')):
        await update.message.reply_text(
            "❌ সঠিক লিংক দিন! (http:// বা https://)",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 মেনুতে ফিরুন", callback_data='main_menu')]
            ])
        )
        return
    
    try:
        progress_msg = await update.message.reply_text(
            "🔥 **লিংক থেকে ডেটা আনছি...**",
            parse_mode='Markdown'
        )
        
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        
        content = response.text
        
        await progress_msg.edit_text("🔍 **ডিকোডিং হচ্ছে...**", parse_mode='Markdown')
        
        decoded = UltimateDecoder.decode_content(content)
        
        orig_size = len(content)
        dec_size = len(decoded)
        size_diff = ((dec_size - orig_size) / orig_size) * 100 if orig_size > 0 else 0
        
        context.user_data['decoded_content'] = decoded
        
        keyboard = [
            [InlineKeyboardButton("📄 ডিকোডেড দেখুন", callback_data='show_decoded')],
            [InlineKeyboardButton("📥 ডাউনলোড করুন", callback_data='download_decoded')],
            [InlineKeyboardButton("🗑️ ডেটা ডিলিট করুন", callback_data='delete_data')],
            [InlineKeyboardButton("🔙 মেনুতে ফিরুন", callback_data='main_menu')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await progress_msg.edit_text(
            f"✅ **লিংক ডিকোড সম্পন্ন!**\n\n"
            f"📊 **রিপোর্ট:**\n"
            f"• ওরিজিনাল: {orig_size / 1024:.2f} KB\n"
            f"• ডিকোডেড: {dec_size / 1024:.2f} KB\n"
            f"• পরিবর্তন: {size_diff:+.2f}%\n"
            f"• সোর্স: `{url[:50]}...`\n\n"
            f"🛡️ **সিকিউরিটি:** ✅ ব্রেক করা হয়েছে",
            parse_mode='Markdown',
            reply_markup=reply_markup
        )
        
    except Exception as e:
        await update.message.reply_text(
            f"❌ **এরর:** {str(e)[:200]}",
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 মেনুতে ফিরুন", callback_data='main_menu')]
            ])
        )

async def handle_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """ফাইল হ্যান্ডলার"""
    doc = update.message.document
    
    try:
        progress_msg = await update.message.reply_text(
            "🔥 **সুপার ডিকোডিং শুরু হচ্ছে...**",
            parse_mode='Markdown'
        )
        
        file = await doc.get_file()
        temp_path = f"temp_{doc.file_name}"
        await file.download_to_drive(temp_path)
        
        await progress_msg.edit_text("🔍 **ডিকোডিং হচ্ছে...**", parse_mode='Markdown')
        
        thumb_path = ThumbnailGenerator.generate_thumbnail(temp_path, doc.file_name, doc.file_size)
        
        decoder = UltimateDecoder()
        output_path, orig_size, dec_size = decoder.decode_file(temp_path)
        
        size_diff = ((dec_size - orig_size) / orig_size) * 100 if orig_size > 0 else 0
        
        ext = os.path.splitext(doc.file_name)[1].lower()
        icon = {'.html': '🌐', '.htm': '🌐', '.xml': '📋', '.json': '📊', '.txt': '📝'}.get(ext, '📄')
        
        caption = (
            f"{icon} **ডিকোড সম্পন্ন!**\n\n"
            f"📄 **ফাইল:** `{doc.file_name}`\n"
            f"📏 **সাইজ:** {doc.file_size / 1024:.1f} KB\n"
            f"🔓 **আউটপুট:** {dec_size / 1024:.2f} KB\n"
            f"📊 **পরিবর্তন:** {size_diff:+.2f}%\n"
            f"🛡️ **সিকিউরিটি:** ✅ ব্রেক করা হয়েছে"
        )
        
        keyboard = [
            [InlineKeyboardButton("📄 ডিকোডেড দেখুন", callback_data='show_decoded')],
            [InlineKeyboardButton("📥 ডাউনলোড করুন", callback_data='download_decoded')],
            [InlineKeyboardButton("🗑️ ফাইল ডিলিট করুন", callback_data='delete_file')],
            [InlineKeyboardButton("🔄 আবার ডিকোড করুন", callback_data='redecode')],
            [InlineKeyboardButton("🔙 মেনুতে ফিরুন", callback_data='main_menu')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        with open(output_path, 'r', encoding='utf-8', errors='ignore') as f:
            context.user_data['decoded_content'] = f.read()
        context.user_data['file_path'] = output_path
        context.user_data['temp_path'] = temp_path
        context.user_data['original_name'] = doc.file_name
        
        if thumb_path and os.path.exists(thumb_path):
            with open(thumb_path, 'rb') as thumb_file:
                await update.message.reply_photo(
                    photo=thumb_file,
                    caption=caption,
                    parse_mode='Markdown',
                    reply_markup=reply_markup
                )
            os.remove(thumb_path)
        else:
            await progress_msg.edit_text(
                caption,
                parse_mode='Markdown',
                reply_markup=reply_markup
            )
        
        await progress_msg.delete()
        
    except Exception as e:
        await update.message.reply_text(
            f"❌ **ডিকোডিং এরর:**\n```\n{str(e)[:300]}\n```",
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 মেনুতে ফিরুন", callback_data='main_menu')]
            ])
        )
        logger.error(f"File handling error: {e}")

async def handle_image(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """ইমেজ হ্যান্ডলার"""
    photo = update.message.photo[-1]
    
    try:
        file = await photo.get_file()
        image_path = f"user_image_{update.message.message_id}.jpg"
        await file.download_to_drive(image_path)
        
        caption = (
            f"🖼️ **আপনার পাঠানো পিক:**\n\n"
            f"📸 সাইজ: {file.file_size / 1024:.1f} KB\n"
            f"📏 ডাইমেনশন: {photo.width} x {photo.height}"
        )
        
        keyboard = [
            [InlineKeyboardButton("🔙 মেনুতে ফিরুন", callback_data='main_menu')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        with open(image_path, 'rb') as f:
            await update.message.reply_photo(
                photo=f,
                caption=caption,
                parse_mode='Markdown',
                reply_markup=reply_markup
            )
        
        os.remove(image_path)
        
    except Exception as e:
        await update.message.reply_text(
            f"❌ ইমেজ এরর: {str(e)[:200]}",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 মেনুতে ফিরুন", callback_data='main_menu')]
            ])
        )

async def show_decoded(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    decoded = context.user_data.get('decoded_content', '')
    
    if not decoded:
        await query.edit_message_text(
            "❌ কোনো ডিকোডেড কন্টেন্ট নেই!",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 মেনুতে ফিরুন", callback_data='main_menu')]
            ])
        )
        return
    
    preview = decoded[:4000]
    if len(decoded) > 4000:
        preview += f"\n\n... (এবং আরও {len(decoded) - 4000} ক্যারেক্টার)"
    
    keyboard = [
        [InlineKeyboardButton("📥 ডাউনলোড করুন", callback_data='download_decoded')],
        [InlineKeyboardButton("🔙 মেনুতে ফিরুন", callback_data='main_menu')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        f"📄 **ডিকোডেড কন্টেন্ট:**\n\n"
        f"```html\n{preview}\n```",
        parse_mode='Markdown',
        reply_markup=reply_markup
    )

async def download_decoded(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    file_path = context.user_data.get('file_path')
    decoded = context.user_data.get('decoded_content')
    original_name = context.user_data.get('original_name', 'decoded')
    
    if file_path and os.path.exists(file_path):
        with open(file_path, 'rb') as f:
            await query.message.reply_document(
                document=f,
                filename=f"DECODED_{original_name}",
                caption="✅ ডিকোডেড ফাইল ডাউনলোড করুন!",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔙 মেনুতে ফিরুন", callback_data='main_menu')]
                ])
            )
    elif decoded:
        temp_file = "decoded_output.txt"
        with open(temp_file, 'w', encoding='utf-8') as f:
            f.write(decoded)
        
        with open(temp_file, 'rb') as f:
            await query.message.reply_document(
                document=f,
                filename=f"DECODED_{original_name}.txt",
                caption="✅ ডিকোডেড ফাইল!",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔙 মেনুতে ফিরুন", callback_data='main_menu')]
                ])
            )
        os.remove(temp_file)
    else:
        await query.edit_message_text(
            "❌ কোনো ডিকোডেড কন্টেন্ট নেই!",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 মেনুতে ফিরুন", callback_data='main_menu')]
            ])
        )

async def delete_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    file_path = context.user_data.get('file_path')
    temp_path = context.user_data.get('temp_path')
    deleted_files = []
    
    if file_path and os.path.exists(file_path):
        os.remove(file_path)
        deleted_files.append("ডিকোডেড ফাইল")
    
    if temp_path and os.path.exists(temp_path):
        os.remove(temp_path)
        deleted_files.append("টেম্প ফাইল")
    
    context.user_data.pop('decoded_content', None)
    context.user_data.pop('file_path', None)
    context.user_data.pop('temp_path', None)
    
    if deleted_files:
        await query.edit_message_text(
            f"🗑️ **ফাইল ডিলিট করা হয়েছে!**\n\n"
            f"ডিলিট করা ফাইল: {', '.join(deleted_files)}",
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 মেনুতে ফিরুন", callback_data='main_menu')]
            ])
        )
    else:
        await query.edit_message_text(
            "❌ ডিলিট করার মতো কোনো ফাইল নেই!",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 মেনুতে ফিরুন", callback_data='main_menu')]
            ])
        )

async def delete_data(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    context.user_data.pop('decoded_content', None)
    await query.edit_message_text(
        "🗑️ **ডেটা ডিলিট করা হয়েছে!**",
        parse_mode='Markdown',
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 মেনুতে ফিরুন", callback_data='main_menu')]
        ])
    )

async def redecode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    file_path = context.user_data.get('file_path')
    
    if file_path and os.path.exists(file_path):
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            
            decoded = UltimateDecoder.decode_content(content)
            context.user_data['decoded_content'] = decoded
            
            keyboard = [
                [InlineKeyboardButton("📄 দেখুন", callback_data='show_decoded')],
                [InlineKeyboardButton("📥 ডাউনলোড", callback_data='download_decoded')],
                [InlineKeyboardButton("🔙 মেনুতে ফিরুন", callback_data='main_menu')]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(
                "🔄 **রি-ডিকোড সম্পন্ন!**\n\n"
                "✅ আবার ডিকোড করা হয়েছে।",
                parse_mode='Markdown',
                reply_markup=reply_markup
            )
        except Exception as e:
            await query.edit_message_text(
                f"❌ রি-ডিকোড এরর: {str(e)[:200]}",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔙 মেনুতে ফিরুন", callback_data='main_menu')]
                ])
            )
    else:
        await query.edit_message_text(
            "❌ রি-ডিকোড করার জন্য ফাইল নেই!",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 মেনুতে ফিরুন", callback_data='main_menu')]
            ])
        )

# ==================== মেইন ====================

def main():
    app = Application.builder().token(TOKEN).build()
    
    # হ্যান্ডলার
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_callback, pattern='^(upload_file|decode_link|show_image|decode_xml|decode_html|delete_files|help_menu|main_menu)$'))
    app.add_handler(CallbackQueryHandler(show_decoded, pattern='^show_decoded$'))
    app.add_handler(CallbackQueryHandler(download_decoded, pattern='^download_decoded$'))
    app.add_handler(CallbackQueryHandler(delete_file, pattern='^delete_file$'))
    app.add_handler(CallbackQueryHandler(delete_data, pattern='^delete_data$'))
    app.add_handler(CallbackQueryHandler(redecode, pattern='^redecode$'))
    app.add_handler(MessageHandler(filters.PHOTO, handle_image))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_link))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_file))
    
    print("🔥 ডিকোডার বট v5.0 চালু হচ্ছে...")
    print("=" * 60)
    print("📌 অপশন সমূহ:")
    print("  • 📤 ফাইল আপলোড")
    print("  • 🔗 লিংক থেকে ডিকোড")
    print("  • 🖼️ ইমেজ দেখান")
    print("  • 📋 XML ডিকোড")
    print("  • 🌐 HTML ডিকোড")
    print("  • 🗑️ ফাইল ডিলিট")
    print("=" * 60)
    app.run_polling()

if __name__ == "__main__":
    main()