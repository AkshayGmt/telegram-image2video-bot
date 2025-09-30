# bot.py
import os
import logging
import requests
from io import BytesIO
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters

# Load .env if present (local dev). On Render/Heroku use real environment variables.
load_dotenv()

LOG = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

# Environment variables (set these in Render/Heroku or .env locally)
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
HF_TOKEN = os.getenv("HF_TOKEN")
# Choose model URL — you can change to another image->video model if desired
# Examples:
# "https://api-inference.huggingface.co/models/ali-vilab/i2vgen-xl"
# "https://api-inference.huggingface.co/models/stabilityai/stable-video-diffusion-img2vid"
HF_MODEL_URL = os.getenv("HF_MODEL_URL", "https://api-inference.huggingface.co/models/ali-vilab/i2vgen-xl")

if not TELEGRAM_TOKEN or not HF_TOKEN:
    LOG.error("Please set TELEGRAM_TOKEN and HF_TOKEN environment variables.")
    raise SystemExit("Missing TELEGRAM_TOKEN or HF_TOKEN")

HEADERS = {"Authorization": f"Bearer {HF_TOKEN}"}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Send me a PHOTO with your description as the PHOTO CAPTION.\n\n"
        "Example caption: a cinematic short video of a golden retriever running on a beach at sunset\n\n"
        "I will return a short realistic video generated from your image and caption."
    )

def call_hf_image_to_video(image_bytes: bytes, prompt: str, timeout=300):
    """
    Tries to call the Hugging Face inference API with an image and prompt.
    The exact accepted payload can vary by model; many image->video HF community models accept
    multipart/form-data with a file field and a prompt field. If a model needs a different format,
    change this function accordingly (see model's README).
    Returns bytes of the resulting video file (mp4/webm/gif).
    """
    # Try multipart first: file -> 'image', data -> 'prompt'
    files = {"image": ("input.jpg", image_bytes, "image/jpeg")}
    data = {"prompt": prompt}

    resp = requests.post(HF_MODEL_URL, headers=HEADERS, files=files, data=data, timeout=timeout)

    if resp.status_code == 200 and resp.content:
        return resp.content

    # If first approach fails, try JSON with base64 image (some endpoints accept JSON)
    try:
        import base64
        b64 = base64.b64encode(image_bytes).decode("utf-8")
        json_payload = {"inputs": {"image": b64, "prompt": prompt}}
        resp2 = requests.post(HF_MODEL_URL, headers=HEADERS, json=json_payload, timeout=timeout)
        if resp2.status_code == 200 and resp2.content:
            return resp2.content
        # else raise the original error for clarity
    except Exception:
        pass

    # Raise with helpful debugging info
    raise RuntimeError(f"HuggingFace API error: status {resp.status_code}, body: {resp.text}")

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    User should send a photo with a caption (caption used as the prompt).
    """
    message = update.message
    if not message.photo:
        await message.reply_text("❌ Please send a photo (not a file).")
        return

    # Best-quality photo
    photo = message.photo[-1]
    caption = (message.caption or "").strip()
    if not caption:
        await message.reply_text(
            "❌ Please include a description as the photo caption.\n"
            "Example caption: 'a subtle dreamlike anim of this portrait, small head turn and blink'"
        )
        return

    await message.reply_text("🎬 Generating video from your photo — this can take 30–120 seconds. Please wait...")

    try:
        f = await photo.get_file()
        # download as bytes
        image_bytes = await f.download_as_bytearray()
        # call HF
        video_bytes = call_hf_image_to_video(bytes(image_bytes), caption)

        # send back video — try as video first, then as document if Telegram rejects
        try:
            await message.reply_video(video=BytesIO(video_bytes), caption="✅ Here is your generated video.")
        except Exception as e:
            LOG.warning("reply_video failed, sending as document: %s", e)
            await message.reply_document(document=BytesIO(video_bytes), filename="output.mp4", caption="✅ Here is your generated video (as file).")

    except Exception as e:
        LOG.exception("Error generating video")
        await message.reply_text(f"⚠️ Error while generating video: {e}")

def main():
    updater = Updater(TELEGRAM_TOKEN, use_context=True)
    dp = updater.dispatcher
    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(MessageHandler(Filters.photo, handle_photo))
    updater.start_polling()
    updater.idle()

if __name__ == "__main__":
    main()



