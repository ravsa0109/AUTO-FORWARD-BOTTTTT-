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

@app.on_message(filters.command("start") & filters.user(OWNER_ID))
async def start(client, message):
    await message.reply("👋 Send target channel message (forwarded), then source first and last message (forwarded).")

@app.on_message(filters.command("reset") & filters.user(OWNER_ID))
async def reset(client, message):
    user_state.pop(message.from_user.id, None)
    await message.reply("🔄 Reset done. Start again by forwarding target message.")

@app.on_message(filters.forwarded & filters.user(OWNER_ID))
async def handle_forward(client, message: Message):
    uid = message.from_user.id

    if not message.forward_from_chat:
        return await message.reply("❌ Not a valid forwarded message.")

    if uid not in user_state:
        user_state[uid] = {"target_chat": message.forward_from_chat.id}
        return await message.reply("✅ Target chat saved. Now send first source message.")

    if "first_msg_id" not in user_state[uid]:
        user_state[uid]["source_chat"] = message.forward_from_chat.id
        user_state[uid]["first_msg_id"] = message.forward_from_message_id
        return await message.reply("✅ First message saved. Now send last message.")

    if "last_msg_id" not in user_state[uid]:
        user_state[uid]["last_msg_id"] = message.forward_from_message_id
        await message.reply("🚀 Starting to forward...")

        source = user_state[uid]["source_chat"]
        target = user_state[uid]["target_chat"]
        first = user_state[uid]["first_msg_id"]
        last = user_state[uid]["last_msg_id"]

        for msg_id in range(first, last + 1):
            try:
                msg = await app.get_messages(source, msg_id)
                await msg.copy(target)
                await asyncio.sleep(1)
            except Exception as e:
                print(f"Failed at {msg_id}: {e}")

        await message.reply("✅ Done forwarding.")
        del user_state[uid]

keep_alive()
app.run()