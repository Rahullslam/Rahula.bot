import os
import telebot
import html
import urllib.parse
import time
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

# আপনার টেলিগ্রাম বটের টোকেন এবং অ্যাডমিন আইডি এখানে বসান
TOKEN = '8783710941:AAEtfegwlNfe50KGC1bSEYo96cLEvhF4f5Y'
ADMIN_ID = ID: 8783710941  # আপনার টেলিগ্রাম আইডি এখানে দিন

bot = telebot.TeleBot(TOKEN)

# /start কমান্ড এবং মূল ইন্টারফেস বাটন
@bot.message_handler(commands=['start'])
def send_welcome(message):
    try:
        markup = InlineKeyboardMarkup()
        decode_button = InlineKeyboardButton("🔓 ফাইল ট্র্যাক ও ডিকোড করুন", callback_data="start_decode_menu")
        markup.add(decode_button)
        
        welcome_text = (
            "👑 **ইউনিভার্সাল ফাইল ট্র্যাক ও ডিকোডার বটে স্বাগতম!**\n\n"
            "যেকোনো ফরম্যাটের ফাইল (HTML, TXT, JS, PHP ইত্যাদি) এখানে সেন্ড করুন। বট স্বয়ংক্রিয়ভাবে ফাইলের ধরন ট্র্যাক করে ডিপ ডিকোড করে দেবে।"
        )
        bot.send_message(message.chat.id, welcome_text, reply_markup=markup, parse_mode="Markdown")
    except Exception as e:
        print(f"Start Error: {e}")

@bot.callback_query_handler(func=lambda call: call.data == "start_decode_menu")
def callback_decode_menu(call):
    try:
        bot.answer_callback_query(call.id, "ফাইল ট্র্যাকিং মোড একটিভ!")
        bot.send_message(
            call.message.chat.id, 
            "📂 এখন আপনার যেকোনো বড় বা হার্ড এনকোডেড ফাইল এই চ্যাটে সেন্ড করুন। আমি ফাইলের ফরম্যাট ট্র্যাক করে ডিকোড শুরু করে দিচ্ছি!"
        )
    except Exception as e:
        print(f"Callback Error: {e}")

# ইউনিভার্সাল ফাইল ট্র্যাকিং এবং ডিপ ডিকোডিং ইঞ্জিন
@bot.message_handler(content_types=['document'])
def handle_docs(message):
    chat_id = message.chat.id
    file_name = None
    output_name = None
    
    try:
        # ফাইলের নাম ও এক্সটেনশন ট্র্যাক করা
        original_file_name = message.document.file_name if message.document.file_name else "unknown_file.txt"
        file_ext = os.path.splitext(original_file_name)[1].lower()
        
        loading_photo_url = "https://images.unsplash.com/photo-1526374965328-7f61d4dc18c5?w=600&auto=format&fit=crop&q=60"
        
        sent_msg = bot.send_photo(
            chat_id, 
            loading_photo_url, 
            caption=f"🔍 **ফাইল ট্র্যাক করা হয়েছে!**\n📂 ফরম্যাট: `{file_ext if file_ext else 'Unknown'}`\n🔐 সিকিউরিটি লক ভেঙে ডিপ ডিকোড চলছে..."
        )
        time.sleep(1.5)

        # ফাইল ডাউনলোড ও প্রসেসিং
        file_info = bot.get_file(message.document.file_id)
        downloaded_file = bot.download_file(file_info.file_path)

        file_name = original_file_name
        with open(file_name, 'wb') as f:
            f.write(downloaded_file)

        # যেকোনো এনকোডেড টেক্সট বা বাইনারি সেফলি রিড করা
        with open(file_name, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()

        # মাল্টি-লেয়ার ডিকোডিং লুপ (যেকোনো ভারী হার্ড কোডিং ভাঙার জন্য)
        for _ in range(5):
            prev = content
            content = html.unescape(content)
            try:
                content = urllib.parse.unquote(content)
            except Exception:
                pass
            if prev == content:
                break

        # আউটপুট ফাইল ফরম্যাট ঠিক রেখে সেভ করা
        output_name = f"decoded_{file_name}"
        with open(output_name, 'w', encoding='utf-8') as f:
            f.write(content)

        # প্রসেসিং মেসেজ রিমুভ করা
        try:
            bot.delete_message(chat_id, sent_msg.message_id)
        except Exception:
            pass

        success_photo_url = "https://images.unsplash.com/photo-1618401471353-b98aedd04e11?w=600&auto=format&fit=crop&q=60"
        
        # সফল ডিকোডিং মেসেজ এবং ফাইল সেন্ড করা
        with open(output_name, 'rb') as f:
            bot.send_photo(
                chat_id, 
                success_photo_url, 
                caption=f"✨ **ফাইল ট্র্যাকিং ও ডিকোডিং সফল!**\n📂 ফাইল টাইপ: `{file_ext}`\nনিচে আপনার ডিকোড করা আসল ফাইলটি দেওয়া হলো:"
            )
            bot.send_document(chat_id, f)

    except Exception as e:
        bot.send_message(chat_id, f"❌ ফাইল প্রসেস করতে গিয়ে ত্রুটি ঘটেছে: {str(e)}")

    finally:
        # সার্ভার ক্লিন রাখা এবং মেমোরি লিক এড়ানোর সেফ লজিক
        try:
            if file_name and os.path.exists(file_name):
                os.remove(file_name)
            if output_name and os.path.exists(output_name):
                os.remove(output_name)
        except Exception as e:
            print(f"Cleanup Error: {e}")

if __name__ == '__main__':
    print("🤖 ইউনিভার্সাল ফাইল ট্র্যাক ও ডিকোডার বট রান হচ্ছে...")
    bot.infinity_polling(skip_pending=True)
