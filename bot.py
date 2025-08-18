import os
import asyncio
from telegram import Bot
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from telegram.constants import ParseMode
from keep_alive import keep_alive

BOT_TOKEN = os.getenv("BOT_TOKEN")
bot = Bot(token=BOT_TOKEN)

SOURCE_CHAT_ID = os.getenv("SOURCE_CHAT_ID")   # example: -100123456789
DEST_CHAT_ID = os.getenv("DEST_CHAT_ID")       # example: -100987654321

# Command: Start
async def start(update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("✅ Bot is running and ready to forward messages!")

# Command: Forward messages (from_msg_id to to_msg_id)
async def forward(update, context: ContextTypes.DEFAULT_TYPE):
    try:
        from_id = int(context.args[0])
        to_id = int(context.args[1])

        await update.message.reply_text(
            f"🚀 Forwarding messages {from_id} to {to_id}..."
        )

        count = 0
        for msg_id in range(from_id, to_id + 1):
            try:
                await bot.copy_message(
                    chat_id=DEST_CHAT_ID,
                    from_chat_id=SOURCE_CHAT_ID,
                    message_id=msg_id
                )
                count += 1

                # small sleep after each 10 forwards
                if count % 10 == 0:
                    await asyncio.sleep(5)

            except Exception as e:
                print(f"❌ Failed to forward {msg_id}: {e}")
                await asyncio.sleep(2)

        await update.message.reply_text(f"✅ Forwarded {count} messages!")

    except Exception as e:
        await update.message.reply_text(f"⚠️ Error: {e}")

def main():
    keep_alive()
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("forward", forward))

    app.run_polling()

if __name__ == "__main__":
    main()
