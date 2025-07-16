from pyrogram import Client, filters
from pyrogram.types import Message
from keep_alive import keep_alive
import os
import asyncio

API_ID = int(os.environ.get("API_ID"))
API_HASH = os.environ.get("API_HASH")
BOT_TOKEN = os.environ.get("BOT_TOKEN")
OWNER_ID = int(os.environ.get("OWNER_ID"))

app = Client("forward_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

user_state = {}
pause_flag = {}
delay_time = {}
replacements = {}
authorized_users = set()
authorized_users.add(OWNER_ID)

@app.on_message(filters.command("start"))
async def start(client, message):
    if message.from_user.id not in authorized_users:
        return await message.reply("⛔ Unauthorized user.")
    await message.reply("👋 Welcome!\\nForward any message from the **target channel** to begin.")

@app.on_message(filters.command("authorize") & filters.user(OWNER_ID))
async def authorize_user(client, message):
    try:
        uid = int(message.text.split()[1])
        authorized_users.add(uid)
        await message.reply(f"✅ Authorized user {uid}")
    except:
        await message.reply("❌ Usage: /authorize <user_id>")

@app.on_message(filters.command("unauthorize") & filters.user(OWNER_ID))
async def unauthorize_user(client, message):
    try:
        uid = int(message.text.split()[1])
        authorized_users.discard(uid)
        await message.reply(f"❌ Unauthorized user {uid}")
    except:
        await message.reply("❌ Usage: /unauthorize <user_id>")

@app.on_message(filters.command("pause") & filters.user(OWNER_ID))
async def pause(client, message):
    pause_flag[OWNER_ID] = True
    await message.reply("⏸ Forwarding paused.")

@app.on_message(filters.command("resume") & filters.user(OWNER_ID))
async def resume(client, message):
    pause_flag[OWNER_ID] = False
    await message.reply("▶️ Forwarding resumed.")

@app.on_message(filters.command("schedule"))
async def set_delay(client, message):
    if message.from_user.id not in authorized_users:
        return
    try:
        seconds = int(message.text.split()[1])
        delay_time[message.from_user.id] = seconds
        await message.reply(f"⏱ Delay set to {seconds} seconds.")
    except:
        await message.reply("❌ Usage: /schedule 5")

@app.on_message(filters.command("settings"))
async def set_replacement(client, message):
    if message.from_user.id not in authorized_users:
        return
    await message.reply("📝 Send word replacement like `Old => New`\\nUse `/clear` to remove all replacements.")

@app.on_message(filters.command("clear"))
async def clear_replacements(client, message):
    uid = message.from_user.id
    if uid not in authorized_users:
        return
    replacements[uid] = {}
    await message.reply("🧽 Cleared all word replacements.")

@app.on_message(filters.text & filters.user(authorized_users))
async def handle_text(client, message: Message):
    uid = message.from_user.id
    text = message.text
    if "=>" in text:
        old, new = text.split("=>")
        if uid not in replacements:
            replacements[uid] = {}
        replacements[uid][old.strip()] = new.strip()
        await message.reply(f"🔁 Replacement set: `{old.strip()}` → `{new.strip()}`")

@app.on_message(filters.forwarded & filters.user(authorized_users))
async def handle_forwarded(client, message: Message):
    uid = message.from_user.id
    if uid not in user_state:
        user_state[uid] = {"target_chat": message.forward_from_chat.id}
        await message.reply("✅ Target chat saved. Now forward **first message** from source channel.")
    elif "first_msg_id" not in user_state[uid]:
        user_state[uid]["source_chat"] = message.forward_from_chat.id
        user_state[uid]["first_msg_id"] = message.forward_from_message_id
        await message.reply("✅ First source message saved. Now forward **last message**.")
    elif "last_msg_id" not in user_state[uid]:
        user_state[uid]["last_msg_id"] = message.forward_from_message_id
        await message.reply("🚀 Starting to forward...")

        sc = user_state[uid]["source_chat"]
        tc = user_state[uid]["target_chat"]
        f_id = user_state[uid]["first_msg_id"]
        l_id = user_state[uid]["last_msg_id"]
        total = l_id - f_id + 1
        pause_flag[uid] = False
        delay = delay_time.get(uid, 0)
        rep = replacements.get(uid, {})

        for idx, msg_id in enumerate(range(f_id, l_id + 1), 1):
            while pause_flag.get(uid, False):
                await asyncio.sleep(1)

            try:
                msg = await app.get_messages(sc, msg_id)

                # Apply replacements to text or caption
                caption = msg.caption
                if msg.text:
                    text = msg.text
                    for old, new in rep.items():
                        text = text.replace(old, new)
                    await app.send_message(tc, text)

                elif caption and (msg.photo or msg.video or msg.document or msg.audio or msg.voice):
                    for old, new in rep.items():
                        caption = caption.replace(old, new)
                    await msg.copy(tc, caption=caption)
                else:
                    await msg.copy(tc)

                if idx % 5 == 0 or idx == total:
                    await message.reply(f"📦 {idx}/{total} messages forwarded.")

                await asyncio.sleep(delay)
            except Exception as e:
                print(f"Error at {msg_id}: {e}")

        await message.reply("✅ Forwarding complete.")
        del user_state[uid]

keep_alive()
app.run()
