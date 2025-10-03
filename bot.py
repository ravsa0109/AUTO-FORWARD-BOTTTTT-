import os
import asyncio
import logging
import ntplib
from time import sleep
from pyrogram import Client, filters
from pyrogram.errors import FloodWait
from keep_alive import keep_alive

API_ID = int(os.environ.get("API_ID"))
API_HASH = os.environ.get("API_HASH")
BOT_TOKEN = os.environ.get("BOT_TOKEN")

logging.basicConfig(level=logging.INFO)

# Store channels in memory
SOURCE = None
TARGETS = []

app = Client(
    "forward-bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
)

# Time sync function
def sync_time():
    try:
        c = ntplib.NTPClient()
        response = c.request('pool.ntp.org')
        offset = response.offset
        print(f"⏰ Time offset: {offset}")
        if abs(offset) > 1:
            print("⚠️ Time drift detected! Restart container if issues persist.")
    except Exception as e:
        print(f"Time sync failed: {e}")

# Commands
@app.on_message(filters.command("start") & filters.private)
async def start(client, message):
    await message.reply("🤖 Auto Forward Bot Active!\n\n"
                        "Use /set_source <chat_id>\n"
                        "Use /add_target <chat_id>\n"
                        "Use /forward <start_id> <end_id>\n"
                        "Use /clear to reset.")

@app.on_message(filters.command("set_source") & filters.private)
async def set_source(client, message):
    global SOURCE
    try:
        SOURCE = int(message.text.split()[1])
        await message.reply(f"✅ Source set to `{SOURCE}`")
    except:
        await message.reply("❌ Usage: /set_source <chat_id>")

@app.on_message(filters.command("add_target") & filters.private)
async def add_target(client, message):
    global TARGETS
    try:
        chat_id = int(message.text.split()[1])
        TARGETS.append(chat_id)
        await message.reply(f"✅ Target added: `{chat_id}`\nNow total: {len(TARGETS)}")
    except:
        await message.reply("❌ Usage: /add_target <chat_id>")

@app.on_message(filters.command("clear") & filters.private)
async def clear(client, message):
    global SOURCE, TARGETS
    SOURCE = None
    TARGETS = []
    await message.reply("🧹 Cleared all sources and targets.")

@app.on_message(filters.command("forward") & filters.private)
async def forward_range(client, message):
    global SOURCE, TARGETS
    if not SOURCE or not TARGETS:
        await message.reply("⚠️ Please set source and targets first.")
        return
    try:
        start_id = int(message.text.split()[1])
        end_id = int(message.text.split()[2])
    except:
        await message.reply("❌ Usage: /forward <start_id> <end_id>")
        return

    await message.reply(f"📤 Forwarding messages {start_id} → {end_id} ...")

    count = 0
    for msg_id in range(start_id, end_id + 1):
        try:
            msg = await client.get_messages(SOURCE, msg_id)
            if msg:
                for target in TARGETS:
                    try:
                        await msg.copy(target)
                    except FloodWait as e:
                        print(f"⏳ FloodWait {e.value} sec")
                        await asyncio.sleep(e.value)
        except Exception as e:
            print(f"⚠️ Failed to forward {msg_id}: {e}")
        count += 1
        if count % 10 == 0:  # every 10 messages, sleep 6 sec
            await asyncio.sleep(6)

    await message.reply("✅ Forward complete!")

# Main loop with retry
async def main():
    sync_time()
    keep_alive()
    while True:
        try:
            await app.start()
            print("✅ Bot started successfully")
            await app.idle()
        except Exception as e:
            print(f"❌ Error: {e}")
            await asyncio.sleep(5)
        finally:
            await app.stop()

if __name__ == "__main__":
    asyncio.run(main())
