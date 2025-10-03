import os
import asyncio
import threading
from pyrogram import Client, filters
from flask import Flask

# Telegram API credentials from Render Environment Variables
API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")

app = Client(
    "forward-bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)

# Store channel IDs
sources = []
destinations = []

# Flask app for keep-alive (Render health check)
flask_app = Flask(__name__)

@flask_app.route('/')
def home():
    return "✅ Forward Bot is Running on Render!"

# Telegram Bot Commands
@app.on_message(filters.command("start") & filters.private)
async def start_cmd(client, message):
    await message.reply(
        "🤖 Forward Bot Ready!\n\n"
        "Commands:\n"
        "`/addsource <id>` - Add source channel\n"
        "`/adddest <id>` - Add destination channel\n"
        "`/clear` - Clear all\n"
        "`/forward <start_id> <end_id>` - Forward messages"
    )

@app.on_message(filters.command("addsource") & filters.private)
async def add_source(client, message):
    try:
        chat_id = int(message.text.split()[1])
        sources.append(chat_id)
        await message.reply(f"✅ Added source: `{chat_id}`")
    except:
        await message.reply("⚠️ Usage: /addsource <chat_id>")

@app.on_message(filters.command("adddest") & filters.private)
async def add_dest(client, message):
    try:
        chat_id = int(message.text.split()[1])
        destinations.append(chat_id)
        await message.reply(f"✅ Added destination: `{chat_id}`")
    except:
        await message.reply("⚠️ Usage: /adddest <chat_id>")

@app.on_message(filters.command("clear") & filters.private)
async def clear(client, message):
    sources.clear()
    destinations.clear()
    await message.reply("🗑 Sources & Destinations cleared.")

@app.on_message(filters.command("forward") & filters.private)
async def forward_cmd(client, message):
    try:
        parts = message.text.split()
        start_id = int(parts[1])
        end_id = int(parts[2])

        if not sources or not destinations:
            await message.reply("⚠️ Add sources & destinations first.")
            return

        for src in sources:
            for msg_id in range(start_id, end_id + 1):
                for dest in destinations:
                    try:
                        await app.copy_message(dest, src, msg_id)
                    except Exception as e:
                        print(f"❌ Failed {msg_id}: {e}")
                        continue

        await message.reply("✅ Forwarding complete.")
    except:
        await message.reply("⚠️ Usage: /forward <start_id> <end_id>")

# Main function
async def main():
    await app.start()
    print("🚀 Bot started successfully on Render!")
    await asyncio.Event().wait()  # Keeps running forever

if __name__ == "__main__":
    threading.Thread(target=lambda: flask_app.run(host="0.0.0.0", port=8080)).start()
    asyncio.run(main())
