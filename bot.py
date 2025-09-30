import os
import logging
import requests
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters

# =============================
# Load from environment variables
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
HF_TOKEN = os.getenv("HF_TOKEN")
HF_MODEL_URL = os.getenv(
    "HF_MODEL_URL",
    "https://api-inference.huggingface.co/models/ali-vilab/i2vgen-xl"
)
# =============================

logging.basicConfig(level=logging.INFO)


# HuggingFace API Request
def generate_video_from_image(image_bytes: bytes, prompt: str, filename="output.mp4"):
    headers = {"Authorization": f"Bearer {HF_TOKEN}"}
    files = {"image": ("input.jpg", image_bytes, "image/jpeg")}
    data = {"prompt": prompt}

    response = requests.post(HF_MODEL_URL, headers=headers, files=files, data=data, timeout=300)

    if response.status_code == 200:
        with open(filename, "wb") as f:
            f.write(response.content)
        return filename
    else:
        raise Exception(f"HuggingFace API error {response.status_code}: {response.text}")


# /start command
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Hi! Send me a photo with a description in the caption.\n\n"
        "Example: upload a selfie with caption *make this person smile*"
    )


# Handle photo upload
async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message
    photo = message.photo[-1]  # Best quality
    caption = message.caption or "A short animation"

    await message.reply_text(f"🎬 Generating video for: {caption} ... please wait ⏳")

    # Download photo
    photo_file = await photo.get_file()
    image_bytes = await photo_file.download_as_bytearray()

    try:
        video_path = generate_video_from_image(image_bytes, caption)
        await message.reply_video(video=open(video_path, "rb"), caption=f"✅ Video for: {caption}")
    except Exception as e:
        await message.reply_text(f"⚠️ Error: {e}")


# Main
def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))

    app.run_polling()


if __name__ == "__main__":
    main()
