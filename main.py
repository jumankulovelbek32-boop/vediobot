import os
import glob
import logging
import asyncio
import threading
from flask import Flask
import telebot
from yt_dlp import YoutubeDL
from shazamio import Shazam

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TOKEN = "8860021658:AAGy3udCnIWA0WxH0_A9-CllZkS2r1pQp24"
bot = telebot.TeleBot(TOKEN)
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot status: 24/7 Alive with Search & Shazam!"

@bot.message_handler(commands=['start'])
def send_welcome(message):
    bot.reply_to(
        message,
        "Salom! Men universal media botman.\n\n"
        "🎬 **Video yuklash:** Link yuboring.\n"
        "🎵 **Qo'shiq izlash:** Nomini yozing.\n"
        "🔍 **Shazam:** Ovozli xabar yuboring."
    )

@bot.message_handler(func=lambda message: True, content_types=['text'])
def handle_text(message):
    text = message.text.strip()
    
    if text.startswith('http://') or text.startswith('https://'):
        msg = bot.reply_to(message, "⏳ Video yuklanmoqda...")
        try:
            ydl_opts = {
                'format': 'best[ext=mp4]/best',
                'outtmpl': '%(id)s.%(ext)s',
                'quiet': True,
                'nocheckcertificate': True,
            }
            with YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(text, download=True)
                filename = ydl.prepare_filename(info)
            
            with open(filename, 'rb') as video:
                bot.send_video(message.chat.id, video)
            if os.path.exists(filename):
                os.remove(filename)
            bot.delete_message(message.chat.id, msg.message_id)
        except Exception as e:
            logger.error(f"Video error: {e}")
            bot.edit_message_text("❌ Videoni yuklab bo'lmadi.", message.chat.id, msg.message_id)
    else:
        msg = bot.reply_to(message, "🔍 Qo'shiq qidirilmoqda...")
        try:
            # YouTube o'rniga SoundCloud orqali qidiruv (blokirovkalarni chetlab o'tadi)
            search_query = f"scsearch1:{text}"
            ydl_opts = {
                'format': 'bestaudio/best',
                'outtmpl': '%(id)s.%(ext)s',
                'quiet': True,
                'nocheckcertificate': True,
            }
            
            with YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(search_query, download=True)
                video_info = info['entries'][0] if 'entries' in info else info
                file_id = video_info['id']
                title = video_info.get('title', text)

            # Faylni qidirib topish
            files = glob.glob(f"{file_id}*")
            if files:
                file_path = files[0]
                with open(file_path, 'rb') as audio:
                    bot.send_audio(message.chat.id, audio, title=title)
                os.remove(file_path)
                bot.delete_message(message.chat.id, msg.message_id)
            else:
                bot.edit_message_text("❌ Audio fayl topilmadi.", message.chat.id, msg.message_id)
        except Exception as e:
            logger.error(f"Audio error: {e}")
            bot.edit_message_text("❌ Musiqa topilmadi yoki yuklab bo'lmadi.", message.chat.id, msg.message_id)

@bot.message_handler(content_types=['voice', 'audio'])
def handle_voice(message):
    msg = bot.reply_to(message, "🔍 Ovoz tahlil qilinmoqda...")
    file_path = "voice.ogg"
    try:
        file_info = bot.get_file(message.voice.file_id if message.voice else message.audio.file_id)
        downloaded_file = bot.download_file(file_info.file_path)
        with open(file_path, 'wb') as f:
            f.write(downloaded_file)
        
        shazam = Shazam()
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        out = loop.run_until_complete(shazam.recognize(file_path))

        track = out.get('track')
        if track:
            title = track.get('title')
            subtitle = track.get('subtitle')
            bot.edit_message_text(f"🎵 Topildi: **{title} - {subtitle}**\nYuklanmoqda...", message.chat.id, msg.message_id)
            
            search_query = f"scsearch1:{title} {subtitle}"
            ydl_opts = {
                'format': 'bestaudio/best',
                'outtmpl': '%(id)s.%(ext)s',
                'quiet': True,
            }
            with YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(search_query, download=True)
                video_info = info['entries'][0] if 'entries' in info else info
                f_id = video_info['id']

            m_files = glob.glob(f"{f_id}*")
            if m_files:
                with open(m_files[0], 'rb') as audio:
                    bot.send_audio(message.chat.id, audio, title=f"{title} - {subtitle}")
                os.remove(m_files[0])
            else:
                bot.send_message(message.chat.id, f"🎵 Musiqa nomi: **{title} - {subtitle}**")
        else:
            bot.edit_message_text("❌ Qo'shiq aniqlanmadi.", message.chat.id, msg.message_id)
    except Exception as e:
        logger.error(f"Shazam error: {e}")
        bot.edit_message_text("❌ Ovozni tanib bo'lmadi.", message.chat.id, msg.message_id)
    finally:
        if os.path.exists(file_path):
            os.remove(file_path)

def run_bot():
    bot.infinity_polling()

if __name__ == "__main__":
    threading.Thread(target=run_bot).start()
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
