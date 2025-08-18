import os
import asyncio
import logging
import re
from telegram import Bot
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from aiohttp import web

# Logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)

# Load ENV
BOT_TOKEN = os.getenv("BOT_TOKEN")
bot = Bot(token=BOT_TOKEN)

# --- Forwarding Function ---
async def forward_messages(update, context: ContextTypes.DEFAULT_TYPE):
    try:
        args = context.args
        if len(args) < 3:
            await update.message.reply_text("Usage: /forward <source_chat_id> <target_chat_id> <start_msg_id>-<end_msg_id>")
            return

        source_chat_id = int(args[0])
        target_chat_id = int(args[1])
        msg_range = args[2].split("-")
        start_msg_id = int(msg_range[0])
        end_msg_id = int(msg_range[1])

        await update.message.reply_text(f"Forwarding {start_msg_id} to {end_msg_id}...")

        count = 0
        for msg_id in range(start_msg_id, end_msg_id + 1):
            try:
                await bot.copy_message(chat_id=target_chat_id, from_chat_id=source_chat_id, message_id=msg_id)

                count += 1
                if count % 10 == 0:
                    logging.info("Sleeping for 5 seconds to prevent overload...")
                    await asyncio.sleep(5)

            except Exception as e:
                logging.error(f"Failed to forward {msg_id}: {e}")
                continue

        await update.message.reply_text("✅ Forwarding completed!")

    except Exception as e:
        logging.error(f"Error: {e}")
        await update.message.reply_text("❌ Something went wrong.")

# --- Start Command ---
async def start(update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🤖 Bot is alive and ready!")

# --- Main Bot ---
def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("forward", forward_messages))
    app.run_polling()

if __name__ == "__main__":
    main()
