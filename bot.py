from pyrogram import Client, filters
from pyrogram.types import Message
from keep_alive import keep_alive
import os
import asyncio

API_ID = int(os.environ.get("API_ID"))
API_HASH = os.environ.get("API_HASH")
BOT_TOKEN = os.environ.get("BOT_TOKEN")
OWNER_ID = int(os.environ.get("OWNER_ID"))  # Only you can control it

app = Client("forward_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

user_state = {}
pause_flag = {}
delay_time = {}
replacements = {}

@app.on_message(filters.command("start"))
async def start(client, message):
    if message.from_user.id != OWNER_ID:
        return await message.reply("⛔ Unauthorized.")
    await message.reply("👋 Welcome!\n1. Forward any message from the **target channel** (where messages will be sent).")

@app.on_message(filters.command("pause"))
async def pause(client, message):
    if message.from_user.id == OWNER_ID:
        pause_flag[OWNER_ID] = True
        await message.reply("⏸ Paused.")

@app.on_message(filters.command("resume"))
async def resume(client, message):
    if message.from_user.id == OWNER_ID:
        pause_flag[OWNER_ID] = False
        await message.reply("▶️ Resumed.")

@app.on_message(filters.command("schedule"))
async def set_delay(client, message):
    if message.from_user.id != OWNER_ID:
        return
    try:
        seconds = int(message.text.split()[1])
        delay_time[OWNER_ID] = seconds
        await message.reply(f"⏱ Delay set to {seconds} seconds between messages.")
    except:
        await message.reply("❌ Usage: /schedule 5")

@app.on_message(filters.command("settings"))
async def set_replacement(client, message):
    if message.from_user.id != OWNER_ID:
        return
    await message.reply("Send word to replace like this:\n`OldWord => NewWord`")

@app.on_message(filters.text & filters.user(OWNER_ID))
async def handle_text(client, message: Message):
    uid = message.from_user.id
    text = message.text

    if "=>" in text:
        old, new = text.split("=>")
        if uid not in replacements:
            replacements[uid] = {}
        replacements[uid][old.strip()] = new.strip()
        await message.reply(f"🔁 Replacement set: `{old.strip()}` → `{new.strip()}`")
        return

@app.on_message(filters.forwarded & filters.user(OWNER_ID))
async def handle_forwarded(client, message: Message):
    uid = message.from_user.id
    if uid not in user_state:
        user_state[uid] = {"target_chat": message.forward_from_chat.id}
        await message.reply("✅ Target channel set.\nNow forward **first message** from the source channel.")
    elif "first_msg_id" not in user_state[uid]:
        user_state[uid]["source_chat"] = message.forward_from_chat.id
        user_state[uid]["first_msg_id"] = message.forward_from_message_id
        await message.reply("✅ First message set.\nNow forward **last message** from the source.")
    elif "last_msg_id" not in user_state[uid]:
        user_state[uid]["last_msg_id"] = message.forward_from_message_id
        await message.reply("⏳ Starting forwarding...")

        sc = user_state[uid]["source_chat"]
        tc = user_state[uid]["target_chat"]
        f_id = user_state[uid]["first_msg_id"]
        l_id = user_state[uid]["last_msg_id"]
        total = l_id - f_id + 1
        pause_flag[uid] = False
        delay = delay_time.get(uid, 0)
        rep = replacements.get(uid, {})

        for idx, msg_id in enumerate(range(f_id, l_id + 1), 1):
            while pause_flag[uid]:
                await asyncio.sleep(1)

            try:
                msg = await app.get_messages(sc, msg_id)
                if msg.text or msg.caption:
                    text = msg.text or msg.caption
                    for old, new in rep.items():
                        text = text.replace(old, new)
                    await app.send_message(tc, text)
                else:
                    await msg.copy(tc)
                if idx % 5 == 0 or idx == total:
                    await message.reply(f"📤 Forwarded {idx}/{total}")
                await asyncio.sleep(delay)
            except Exception as e:
                print(f"Failed at {msg_id}: {e}")

        await message.reply("✅ All messages forwarded.")
        del user_state[uid]

keep_alive()
app.run()
