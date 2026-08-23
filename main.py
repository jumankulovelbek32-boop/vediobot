import os
import glob
import logging
import asyncio
import threading
from flask import Flask
import telebot
from yt_dlp import YoutubeDL
from shazamio import Shazam

# =========================
# SETTINGS
# =========================
TOKEN = os.environ.get("TOKEN")

if not TOKEN:
    raise RuntimeError("TOKEN environment variable is not set in Render.")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)
logger = logging.getLogger(__name__)

bot = telebot.TeleBot(TOKEN, parse_mode="Markdown")
app = Flask(__name__)

DOWNLOAD_DIR = "downloads"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)


# =========================
# RENDER HEALTH CHECK
# =========================
@app.route("/")
def home():
    return "Bot status: ONLINE"


@app.route("/health")
def health():
    return "OK"


# =========================
# /start
# =========================
@bot.message_handler(commands=["start"])
def send_welcome(message):
    bot.reply_to(
        message,
        "Salom! Men universal media botman! 🚀\n\n"
        "🎬 *Video yuklash:* Instagram, TikTok, YouTube yoki boshqa media linkini yuboring.\n\n"
        "🎵 *Qo‘shiq izlash:* Qo‘shiq nomi yoki ijrochini yozing.\n\n"
        "🔍 *Shazam:* Ovozli xabar yoki audio yuboring."
    )


# =========================
# DOWNLOAD VIDEO
# =========================
def download_video(url):
    ydl_opts = {
        "format": "best[ext=mp4]/best",
        "outtmpl": os.path.join(DOWNLOAD_DIR, "%(id)s.%(ext)s"),
        "quiet": True,
        "noplaylist": True,
        "nocheckcertificate": True,
        "retries": 2,
    }

    with YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        filename = ydl.prepare_filename(info)

    return filename


# =========================
# SEARCH/DOWNLOAD AUDIO
# =========================
def download_audio(query):
    ydl_opts = {
        "format": "bestaudio/best",
        "outtmpl": os.path.join(DOWNLOAD_DIR, "%(id)s.%(ext)s"),
        "quiet": True,
        "noplaylist": True,
        "nocheckcertificate": True,
        "retries": 2,
    }

    with YoutubeDL(ydl_opts) as ydl:
        # yt-dlp's search extractor
        info = ydl.extract_info(
            f"ytsearch1:{query}",
            download=True
        )

        if "entries" in info:
            entries = [x for x in info["entries"] if x]
            if not entries:
                raise RuntimeError("Audio topilmadi.")
            track = entries[0]
        else:
            track = info

        title = track.get("title", query)
        filename = ydl.prepare_filename(track)

    return filename, title


# =========================
# TEXT / LINKS
# =========================
@bot.message_handler(
    func=lambda message: True,
    content_types=["text"]
)
def handle_text(message):
    text = (message.text or "").strip()

    if not text:
        return

    # URL -> video/media
    if text.startswith(("http://", "https://")):
        msg = bot.reply_to(message, "⏳ Media yuklanmoqda...")

        try:
            filename = download_video(text)

            if not os.path.exists(filename):
                raise RuntimeError("Yuklangan fayl topilmadi.")

            # Telegram Bot API uchun amaliy limit
            file_size = os.path.getsize(filename)
            if file_size > 49 * 1024 * 1024:
                bot.edit_message_text(
                    "❌ Fayl juda katta. Telegram bot orqali yuborish uchun "
                    "kichikroq video/link kerak.",
                    message.chat.id,
                    msg.message_id
                )
                return

            with open(filename, "rb") as video:
                bot.send_video(
                    message.chat.id,
                    video,
                    supports_streaming=True
                )

            bot.delete_message(message.chat.id, msg.message_id)

        except Exception as e:
            logger.exception("Video error: %s", e)
            try:
                bot.edit_message_text(
                    "❌ Videoni yuklab bo‘lmadi.\n\n"
                    "Link ishlamasligi yoki platforma cheklovi bo‘lishi mumkin.",
                    message.chat.id,
                    msg.message_id
                )
            except Exception:
                pass

        finally:
            # downloads papkasidagi vaqtinchalik fayllarni tozalash
            for f in glob.glob(os.path.join(DOWNLOAD_DIR, "*")):
                try:
                    if os.path.isfile(f):
                        os.remove(f)
                except Exception:
                    pass

        return

    # Text -> music search
    msg = bot.reply_to(message, "🔍 Qo‘shiq qidirilmoqda...")

    try:
        filename, title = download_audio(text)

        if not os.path.exists(filename):
            raise RuntimeError("Audio fayl topilmadi.")

        file_size = os.path.getsize(filename)
        if file_size > 49 * 1024 * 1024:
            raise RuntimeError("Audio fayli juda katta.")

        with open(filename, "rb") as audio:
            bot.send_audio(
                message.chat.id,
                audio,
                title=title
            )

        bot.delete_message(message.chat.id, msg.message_id)

    except Exception as e:
        logger.exception("Audio error: %s", e)
        try:
            bot.edit_message_text(
                "❌ Musiqa topilmadi yoki yuklab bo‘lmadi.",
                message.chat.id,
                msg.message_id
            )
        except Exception:
            pass

    finally:
        for f in glob.glob(os.path.join(DOWNLOAD_DIR, "*")):
            try:
                if os.path.isfile(f):
                    os.remove(f)
            except Exception:
                pass


# =========================
# SHAZAM
# =========================
async def recognize_song(file_path):
    shazam = Shazam()
    return await shazam.recognize(file_path)


@bot.message_handler(content_types=["voice", "audio"])
def handle_voice(message):
    msg = bot.reply_to(message, "🔍 Ovoz tahlil qilinmoqda...")

    file_path = os.path.join(
        DOWNLOAD_DIR,
        f"voice_{message.message_id}.ogg"
    )

    try:
        file_id = (
            message.voice.file_id
            if message.voice
            else message.audio.file_id
        )

        file_info = bot.get_file(file_id)
        downloaded_file = bot.download_file(file_info.file_path)

        with open(file_path, "wb") as f:
            f.write(downloaded_file)

        result = asyncio.run(recognize_song(file_path))
        track = result.get("track") if result else None

        if not track:
            bot.edit_message_text(
                "❌ Qo‘shiq aniqlanmadi.",
                message.chat.id,
                msg.message_id
            )
            return

        title = track.get("title", "Noma'lum")
        subtitle = track.get("subtitle", "Noma'lum ijrochi")

        bot.edit_message_text(
            f"🎵 *Topildi:* {title} — {subtitle}\n"
            "⏳ Yuklanmoqda...",
            message.chat.id,
            msg.message_id
        )

        try:
            filename, _ = download_audio(f"{title} {subtitle}")

            if os.path.exists(filename):
                file_size = os.path.getsize(filename)

                if file_size <= 49 * 1024 * 1024:
                    with open(filename, "rb") as audio:
                        bot.send_audio(
                            message.chat.id,
                            audio,
                            title=f"{title} - {subtitle}"
                        )
                else:
                    bot.send_message(
                        message.chat.id,
                        f"🎵 *Qo‘shiq:* {title} - {subtitle}\n"
                        "❌ Audio fayli juda katta."
                    )
            else:
                bot.send_message(
                    message.chat.id,
                    f"🎵 *Qo‘shiq:* {title} - {subtitle}"
                )

        except Exception as e:
            logger.exception("Shazam audio download error: %s", e)
            bot.send_message(
                message.chat.id,
                f"🎵 *Topildi:* {title} - {subtitle}\n"
                "⚠️ Qo‘shiqni yuklab bo‘lmadi."
            )

    except Exception as e:
        logger.exception("Shazam error: %s", e)
        try:
            bot.edit_message_text(
                "❌ Ovozni tanib bo‘lmadi.",
                message.chat.id,
                msg.message_id
            )
        except Exception:
            pass

    finally:
        for f in glob.glob(os.path.join(DOWNLOAD_DIR, "*")):
            try:
                if os.path.isfile(f):
                    os.remove(f)
            except Exception:
                pass


# =========================
# TELEGRAM POLLING
# =========================
def run_bot():
    logger.info("Telegram bot starting...")

    try:
        # Eski webhook bo‘lsa olib tashlaymiz.
        try:
            bot.remove_webhook()
        except Exception as e:
            logger.warning("Webhook remove warning: %s", e)

        logger.info("Bot is ready. Starting polling...")

        bot.infinity_polling(
            timeout=30,
            long_polling_timeout=30,
            skip_pending=True,
            allowed_updates=["message"]
        )

    except Exception as e:
        logger.exception("Polling stopped: %s", e)
        raise


# =========================
# MAIN
# =========================
if __name__ == "__main__":
    bot_thread = threading.Thread(
        target=run_bot,
        daemon=True
    )
    bot_thread.start()

    port = int(os.environ.get("PORT", "10000"))

    # Render health server
    app.run(
        host="0.0.0.0",
        port=port,
        debug=False,
        use_reloader=False
    )
