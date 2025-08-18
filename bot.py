import os
import asyncio
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

BOT_TOKEN = os.getenv("BOT_TOKEN")

# In-memory storage
user_data = {}

# Start command
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Welcome!\n\n"
        "Use /setsource <channel_id> to set source channel\n"
        "Use /setdest <channel_id> to set destination channel\n"
        "Use /forward <start_id> <end_id> to forward messages\n\n"
        "Example:\n/setsource -1001234567890\n/setdest -1009876543210\n/forward 10 50"
    )

# Set source channel
async def set_source(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("⚠️ Usage: /setsource <channel_id>")
        return
    user_data["source"] = int(context.args[0])
    await update.message.reply_text(f"✅ Source channel set to {context.args[0]}")

# Set destination channel
async def set_dest(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("⚠️ Usage: /setdest <channel_id>")
        return
    user_data["dest"] = int(context.args[0])
    await update.message.reply_text(f"✅ Destination channel set to {context.args[0]}")

# Forward messages
async def forward_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if "source" not in user_data or "dest" not in user_data:
        await update.message.reply_text("⚠️ Please set source and destination first using /setsource and /setdest")
        return

    if len(context.args) < 2:
        await update.message.reply_text("⚠️ Usage: /forward <start_id> <end_id>")
        return

    source = user_data["source"]
    dest = user_data["dest"]
    start_id = int(context.args[0])
    end_id = int(context.args[1])

    await update.message.reply_text(f"🚀 Starting forward from {start_id} to {end_id}...")

    count = 0
    for msg_id in range(start_id, end_id + 1):
        try:
            msg = await context.bot.forward_message(
                chat_id=dest,
                from_chat_id=source,
                message_id=msg_id
            )

            # Remove forward tag by copying
            await context.bot.copy_message(
                chat_id=dest,
                from_chat_id=source,
                message_id=msg_id
            )
            await context.bot.delete_message(chat_id=dest, message_id=msg.message_id)

            count += 1

            # Sleep after every 10 messages
            if count % 10 == 0:
                await update.message.reply_text(f"⏸️ Paused 6s after {count} messages...")
                await asyncio.sleep(6)

        except Exception as e:
            await update.message.reply_text(f"⚠️ Failed at {msg_id}: {e}")
            continue

    await update.message.reply_text("✅ Forward complete!")

def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("setsource", set_source))
    app.add_handler(CommandHandler("setdest", set_dest))
    app.add_handler(CommandHandler("forward", forward_messages))

    app.run_polling()

if __name__ == "__main__":
    main()
