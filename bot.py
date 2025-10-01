import os
import asyncio
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

BOT_TOKEN = os.getenv("BOT_TOKEN")

# In-memory storage
user_data = {
    "source": None,
    "destinations": []
}

# Start command
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Welcome!\n\n"
        "Use /setsource <channel_id> to set source channel\n"
        "Use /adddest <channel_id> to add destination channel\n"
        "Use /listdest to see all destination channels\n"
        "Use /forward <start_id> <end_id> to forward messages\n\n"
        "Example:\n/setsource -1001234567890\n/adddest -1009876543210\n/adddest -1005555555555\n/forward 10 50"
    )

# Set source channel
async def set_source(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("⚠️ Usage: /setsource <channel_id>")
        return
    user_data["source"] = int(context.args[0])
    await update.message.reply_text(f"✅ Source channel set to {context.args[0]}")

# Add destination channel
async def add_dest(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("⚠️ Usage: /adddest <channel_id>")
        return
    dest_id = int(context.args[0])
    if dest_id not in user_data["destinations"]:
        user_data["destinations"].append(dest_id)
        await update.message.reply_text(f"✅ Added destination channel: {dest_id}")
    else:
        await update.message.reply_text("⚠️ This channel is already in destination list.")

# List destinations
async def list_dest(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not user_data["destinations"]:
        await update.message.reply_text("⚠️ No destinations set yet.")
        return
    dests = "\n".join(str(d) for d in user_data["destinations"])
    await update.message.reply_text(f"📌 Destination channels:\n{dests}")

# Forward messages
async def forward_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not user_data["source"] or not user_data["destinations"]:
        await update.message.reply_text("⚠️ Please set source and at least one destination using /setsource and /adddest")
        return

    if len(context.args) < 2:
        await update.message.reply_text("⚠️ Usage: /forward <start_id> <end_id>")
        return

    source = user_data["source"]
    destinations = user_data["destinations"]
    start_id = int(context.args[0])
    end_id = int(context.args[1])

    await update.message.reply_text(
        f"🚀 Starting forward from {start_id} to {end_id}...\n"
        f"📌 Destinations: {len(destinations)} channels"
    )

    count = 0
    for msg_id in range(start_id, end_id + 1):
        try:
            for dest in destinations:
                # Copy message (no forward tag)
                await context.bot.copy_message(
                    chat_id=dest,
                    from_chat_id=source,
                    message_id=msg_id
                )
                await asyncio.sleep(1)  # 1s gap per message per channel

            count += 1

            # Sleep after every 10 messages (extra flood safety)
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
    app.add_handler(CommandHandler("adddest", add_dest))
    app.add_handler(CommandHandler("listdest", list_dest))
    app.add_handler(CommandHandler("forward", forward_messages))

    app.run_polling()

if __name__ == "__main__":
    main()
