import os
import asyncio
from pyrogram import Client, filters
from flask import Flask

API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")

app = Client(
    "forward-bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)

# Store source & destination channels in memory
sources = []
destinations = []

# Flask app for keep-alive
flask_app = Flask(__name__)

@flask_app.route('/')
def home():
    return "✅ Bot is running!"

# Commands
@app.on_message(filters.command("start") & filters.private)
async def start(client, message):
    await message.reply("🤖 Bot is alive!\n\nUse:\n`/addsource id`\n`/adddest id`\n`/clear`\n`/forward 1 100`")

@app.on_message(filters.command("addsource") & filters.private)
async def add_source(client, message):
    try:
        chat_id = int(message.text.split()[1])
        sources.append(chat_id)
        await message.reply(f"✅ Source added: `{chat_id}`")
    except:
        await message.reply("⚠️ Usage: /addsource chat_id")

@app.on_message(filters.command("adddest") & filters.private)
async def add_dest(client, message):
    try:
        chat_id = int(message.text.split()[1])
        destinations.append(chat_id)
        await message.reply(f"✅ Destination added: `{chat_id}`")
    except:
        await message.reply("⚠️ Usage: /adddest chat_id")

@app.on_message(filters.command("clear") & filters.private)
async def clear(client, message):
    sources.clear()
    destinations.clear()
    await message.reply("🗑 Cleared all sources and destinations.")

@app.on_message(filters.command("forward") & filters.private)
async def forward_messages(client, message):
    try:
        parts = message.text.split()
        start_id = int(parts[1])
        end_id = int(parts[2])

        if not sources or not destinations:
            await message.reply("⚠️ Add source and destination first!")
            return

        for src in sources:
            for msg_id in range(start_id, end_id + 1):
                try:
                    for dest in destinations:
                        await app.copy_message(
                            chat_id=dest,
                            from_chat_id=src,
                            message_id=msg_id
                        )
                except Exception as e:
                    print(f"❌ Failed to forward {msg_id}: {e}")
                    continue

        await message.reply("✅ Forward complete.")
    except:
        await message.reply("⚠️ Usage: /forward start_id end_id")

async def main():
    await app.start()
    print("✅ Bot started successfully")

    # keep alive loop
    loop_event = asyncio.Event()
    await loop_event.wait()

if __name__ == "__main__":
    import threading
    threading.Thread(target=lambda: flask_app.run(host="0.0.0.0", port=8080)).start()
    asyncio.run(main())
