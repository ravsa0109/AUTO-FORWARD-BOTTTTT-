from pyrogram import Client, filters
from pyrogram.types import Message
from keep_alive import keep_alive
import os
import asyncio
import json

API_ID = int(os.environ.get("API_ID")) API_HASH = os.environ.get("API_HASH") BOT_TOKEN = os.environ.get("BOT_TOKEN") OWNER_ID = int(os.environ.get("OWNER_ID")) DB_CHANNEL = int(os.environ.get("DB_CHANNEL"))  # Add this to your Render env

app = Client("forward_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

Storage

user_state = {} pause_flag = {} delay_time = {} replacements = {} authorized_users = set() AUTHORIZED_FILE = "authorized_users.json"

Load authorized users from file

def load_users(): global authorized_users try: with open(AUTHORIZED_FILE, "r") as f: authorized_users = set(json.load(f)) except: authorized_users = set([OWNER_ID]) save_users()

Save authorized users to file

def save_users(): with open(AUTHORIZED_FILE, "w") as f: json.dump(list(authorized_users), f)

load_users()

@app.on_message(filters.command("start")) async def start(client, message): if message.from_user.id not in authorized_users: return await message.reply("⛔ Unauthorized user.") await message.reply("👋 Welcome!\n\nCommands:\n/start\n/reset\n/pause, /resume\n/schedule <sec>\n/settings, /clear\n/authorize <id>, /unauthorize <id>\n/listusers\n/replacements")

@app.on_message(filters.command("authorize") & filters.user(OWNER_ID)) async def authorize_user(client, message): args = message.text.split() if len(args) != 2 or not args[1].isdigit(): return await message.reply("❌ Usage: /authorize <user_id>") uid = int(args[1]) if uid in authorized_users: return await message.reply(f"ℹ️ User {uid} is already authorized.") authorized_users.add(uid) save_users() await message.reply(f"✅ User {uid} has been authorized.")

@app.on_message(filters.command("unauthorize") & filters.user(OWNER_ID)) async def unauthorize_user(client, message): args = message.text.split() if len(args) != 2 or not args[1].isdigit(): return await message.reply("❌ Usage: /unauthorize <user_id>") uid = int(args[1]) if uid not in authorized_users: return await message.reply(f"ℹ️ User {uid} is not authorized.") authorized_users.remove(uid) save_users() await message.reply(f"🚫 User {uid} has been unauthorized.")

@app.on_message(filters.command("listusers") & filters.user(OWNER_ID)) async def list_users(client, message): await message.reply("👥 Authorized Users:\n" + "\n".join(map(str, authorized_users)))

@app.on_message(filters.command("replacements") & filters.user(list(authorized_users))) async def show_replacements(client, message): uid = message.from_user.id rep = replacements.get(uid, {}) if not rep: return await message.reply("❌ No replacements set.") msg = "🔁 Your replacements:\n" for k, v in rep.items(): msg += f"{k} => {v}\n" await message.reply(msg)

@app.on_message(filters.command("pause") & filters.user(OWNER_ID)) async def pause(client, message): pause_flag[OWNER_ID] = True await message.reply("⏸ Forwarding paused.")

@app.on_message(filters.command("resume") & filters.user(OWNER_ID)) async def resume(client, message): pause_flag[OWNER_ID] = False await message.reply("▶️ Forwarding resumed.")

@app.on_message(filters.command("schedule")) async def set_delay(client, message): if message.from_user.id not in authorized_users: return try: seconds = int(message.text.split()[1]) delay_time[message.from_user.id] = seconds await message.reply(f"⏱ Delay set to {seconds} seconds.") except: await message.reply("❌ Usage: /schedule 5")

@app.on_message(filters.command("settings")) async def set_replacement(client, message): if message.from_user.id not in authorized_users: return await message.reply("📝 Send word replacement like Old => New\nUse /clear to remove all replacements.")

@app.on_message(filters.command("clear")) async def clear_replacements(client, message): uid = message.from_user.id if uid not in authorized_users: return replacements[uid] = {} await message.reply("🧽 Cleared all word replacements.")

@app.on_message(filters.command("reset") & filters.user(list(authorized_users))) async def reset_user_state(client, message): uid = message.from_user.id user_state.pop(uid, None) await message.reply("🔄 Forwarding state has been reset. Forward target message again.")

@app.on_message(filters.text & filters.user(list(authorized_users))) async def handle_text(client, message: Message): uid = message.from_user.id text = message.text if "=>" in text: old, new = text.split("=>") if uid not in replacements: replacements[uid] = {} replacements[uid][old.strip()] = new.strip() await message.reply(f"🔁 Replacement set: {old.strip()} → {new.strip()}")

@app.on_message(filters.forwarded & filters.user(list(authorized_users))) async def handle_forwarded(client, message: Message): uid = message.from_user.id if uid not in user_state: user_state[uid] = {"target_chat": message.forward_from_chat.id} await message.reply("✅ Target chat saved. Now forward first message from source channel.") elif "first_msg_id" not in user_state[uid]: user_state[uid]["source_chat"] = message.forward_from_chat.id user_state[uid]["first_msg_id"] = message.forward_from_message_id await message.reply("✅ First source message saved. Now forward last message.") elif "last_msg_id" not in user_state[uid]: user_state[uid]["last_msg_id"] = message.forward_from_message_id await message.reply("🚀 Starting to forward...")

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
            caption = msg.caption
            if msg.text:
                text = msg.text
                for old, new in rep.items():
                    text = text.replace(old, new)
                await app.send_message(tc, text)
                await app.send_message(DB_CHANNEL, text)
            elif caption and (msg.photo or msg.video or msg.document or msg.audio or msg.voice):
                for old, new in rep.items():
                    caption = caption.replace(old, new)
                await msg.copy(tc, caption=caption)
                await msg.copy(DB_CHANNEL, caption=caption)
            else:
                await msg.copy(tc)
                await msg.copy(DB_CHANNEL)

            if idx % 5 == 0 or idx == total:
                await message.reply(f"📦 {idx}/{total} messages forwarded.")

            await asyncio.sleep(delay)
        except Exception as e:
            print(f"Error at {msg_id}: {e}")

    await message.reply("✅ Forwarding complete.")
    del user_state[uid]

keep_alive() app.run()

