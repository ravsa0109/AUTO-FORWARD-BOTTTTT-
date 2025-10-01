import os
import asyncio
from pyrogram import Client, filters
from keep_alive import keep_alive

# ================== ENV VARS ==================
API_ID = int(os.environ.get("API_ID"))
API_HASH = os.environ.get("API_HASH")
BOT_TOKEN = os.environ.get("BOT_TOKEN")
OWNER_ID = int(os.environ.get("OWNER_ID"))

# create client
app = Client("forward-bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# ================== COMMANDS ==================
@app.on_message(filters.command("start") & filters.private)
async def start(client, message):
    await message.reply_text(
        "👋 Hi! I'm a Forward Bot.\n\n"
        "Use this format:\n"
        "`/forward <source_chat_id> <target_chat_id> <start_msg_id>-<end_msg_id>`\n\n"
        "Example:\n`/forward -1001234567890 -1009876543210 10-50`"
    )

@app.on_message(filters.command("forward") & filters.user(OWNER_ID))
async def forward_messages(client, message):
    try:
        parts = message.text.split()
        if len(parts) != 4:
            return await message.reply("❌ Wrong format.\n\nUsage:\n`/forward <source_chat_id> <target_chat_id> <start_msg_id>-<end_msg_id>`")

        source_chat = int(parts[1])
        target_chat = int(parts[2])
        msg_range = parts[3].split("-")
        start_id, end_id = int(msg_range[0]), int(msg_range[1])

        await message.reply(f"📤 Forwarding messages {start_id} → {end_id}...")

        count = 0
        for msg_id in range(start_id, end_id + 1):
            try:
                await client.copy_message(chat_id=target_chat, from_chat_id=source_chat, message_id=msg_id)
                count += 1
            except Exception as e:
                print(f"Error on {msg_id}: {e}")
            # floodwait handling → sleep every 10 messages
            if count % 10 == 0:
                await asyncio.sleep(6)

        await message.reply(f"✅ Forwarding done! ({count} messages)")

    except Exception as e:
        await message.reply(f"⚠️ Error: {e}")

# ================== START ==================
keep_alive()
app.run()
