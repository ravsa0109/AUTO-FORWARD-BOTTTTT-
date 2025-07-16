from pyrogram import Client, filters
from pyrogram.types import Message
from keep_alive import keep_alive
import os

API_ID = int(os.environ.get("API_ID"))
API_HASH = os.environ.get("API_HASH")
BOT_TOKEN = os.environ.get("BOT_TOKEN")

app = Client("forward_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

user_state = {}

@app.on_message(filters.command("start"))
async def start(client, message):
    await message.reply("👋 Welcome!\n1. Please forward **any message from the target channel** (where messages will be sent).")

@app.on_message(filters.forwarded)
async def handle_forwarded(client, message: Message):
    user_id = message.from_user.id

    if user_id not in user_state:
        user_state[user_id] = {"target_chat": message.forward_from_chat.id}
        await message.reply("✅ Target channel set.\nNow forward **first message** from the source channel.")

    elif "first_msg_id" not in user_state[user_id]:
        user_state[user_id]["source_chat"] = message.forward_from_chat.id
        user_state[user_id]["first_msg_id"] = message.forward_from_message_id
        await message.reply("✅ First source message received.\nNow forward **last message** from the same source channel.")

    elif "last_msg_id" not in user_state[user_id]:
        user_state[user_id]["last_msg_id"] = message.forward_from_message_id
        await message.reply("⏳ Forwarding messages...")

        sc = user_state[user_id]["source_chat"]
        tc = user_state[user_id]["target_chat"]
        f_id = user_state[user_id]["first_msg_id"]
        l_id = user_state[user_id]["last_msg_id"]

        for msg_id in range(f_id, l_id + 1):
            try:
                msg = await app.get_messages(sc, msg_id)
                await msg.copy(tc)
            except Exception as e:
                print(f"Error copying message {msg_id}: {e}")

        await message.reply("✅ All messages forwarded successfully!")
        del user_state[user_id]

keep_alive()
app.run()
