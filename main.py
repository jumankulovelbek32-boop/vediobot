import os
import asyncio
import threading
from flask import Flask
import telebot
import yt_dlp
from shazamio import Shazam

app = Flask(__name__)

@app.route('/')
def home():
    return "Bot status: 24/7 Alive with Search & Shazam!"
TOKEN = "8860021658:AAGy3udCnIWA0WxH0cdewn9479n4j4a-kSo"
bot = telebot.TeleBot(TOKEN)
shazam = Shazam()

@bot.message_handler(commands=['start'])
def send_welcome(message):
    bot.reply_to(
        message, 
        "Salom! Men universal media botman! 🚀\n\n"
        "🎬 **Video yuklash:** Instagram, TikTok yoki YouTube linkini yuboring.\n"
        "🎵 **Qo'shiq izlash:** Shunchaki qo'shiq nomini yoki ijrochini yozing.\n"
        "🔍 **Shazam:** Ovozli xabar (voice) yoki video yuboring, qo'shiqni topib beraman!"
    )

# 1. LINK YUBORILGANDA VIDEO YUKLASH
@bot.message_handler(func=lambda message: message.text and message.text.startswith("http"))
def download_media(message):
    url = message.text.strip()
    status_msg = bot.reply_to(message, "⏳ Video yuklanmoqda...")
    file_path = f"video_{message.from_user.id}.mp4"

    try:
        ydl_opts = {
            'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
            'outtmpl': file_path,
            'quiet': True,
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])

        with open(file_path, 'rb') as video_file:
            bot.send_video(message.chat.id, video_file, caption="Video tayyor! 🎬")
        bot.delete_message(message.chat.id, status_msg.message_id)

    except Exception as e:
        bot.edit_message_text("❌ Videoni yuklab bo'lmadi.", message.chat.id, status_msg.message_id)
    finally:
        if os.path.exists(file_path):
            os.remove(file_path)

# 2. QO'SHIQ NOMINI YOZGANINI ANIQLASH VA MP3 QILIB YUKLASH
@bot.message_handler(func=lambda message: message.text and not message.text.startswith("/"))
def search_and_download_music(message):
    query = message.text.strip()
    status_msg = bot.reply_to(message, f"🔍 `{query}` bo'yicha musiqa qidirilmoqda...", parse_mode="Markdown")
    file_path = f"music_{message.from_user.id}.mp3"

    try:
        ydl_opts = {
            'format': 'bestaudio/best',
            'outtmpl': file_path,
            'default_search': 'ytsearch1:',  # YouTube'dan birinchi chiqqan natijani olish
            'quiet': True,
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(query, download=True)
            title = info['entries'][0]['title'] if 'entries' in info else info.get('title', 'Musiqa')

        with open(file_path, 'rb') as audio_file:
            bot.send_audio(message.chat.id, audio_file, caption=f"🎵 {title}")
        
        bot.delete_message(message.chat.id, status_msg.message_id)

    except Exception as e:
        print(f"Xatolik: {e}")
        bot.edit_message_text("❌ Musiqa topilmadi yoki yuklab bo'lmadi.", message.chat.id, status_msg.message_id)
    finally:
        if os.path.exists(file_path):
            os.remove(file_path)

# 3. SHAZAM (AUDIO, VOICE YOKI VIDEO YUBORILGANDA)
@bot.message_handler(content_types=['voice', 'audio', 'video', 'video_note'])
def recognize_music(message):
    status_msg = bot.reply_to(message, "🔍 Qo'shiq aniqlanmoqda (Shazam)...")
    file_path = f"media_{message.from_user.id}.mp3"

    try:
        if message.content_type == 'voice':
            file_info = bot.get_file(message.voice.file_id)
        elif message.content_type == 'audio':
            file_info = bot.get_file(message.audio.file_id)
        elif message.content_type == 'video':
            file_info = bot.get_file(message.video.file_id)
        elif message.content_type == 'video_note':
            file_info = bot.get_file(message.video_note.file_id)

        downloaded_file = bot.download_file(file_info.file_path)
        with open(file_path, 'wb') as new_file:
            new_file.write(downloaded_file)

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        out = loop.run_until_complete(shazam.recognize(file_path))

        track = out.get('track')
        if track:
            title = track.get('title', 'Noma\'lum')
            subtitle = track.get('subtitle', 'Noma\'lum')
            caption = f"🎵 **Topilgan qo'shiq:**\n\n📌 **Nomi:** {title}\n👤 **Ijrochi:** {subtitle}\n\n*Yuklab olish uchun qo'shiq nomini text qilib yuboring!*"
            bot.reply_to(message, caption, parse_mode="Markdown")
        else:
            bot.reply_to(message, "❌ Qo'shiq aniqlanmadi.")

        bot.delete_message(message.chat.id, status_msg.message_id)

    except Exception as e:
        bot.edit_message_text("❌ Xatolik yuz berdi.", message.chat.id, status_msg.message_id)
    finally:
        if os.path.exists(file_path):
            os.remove(file_path)

def run_bot():
    bot.infinity_polling()

if __name__ == "__main__":
    threading.Thread(target=run_bot).start()
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)

