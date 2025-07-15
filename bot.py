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
    await message.reply("👋 Welcome! Send the **target channel** message link where you want to forward messages.")

@app.on_message(filters.text)
async def handle_links(client, message: Message):
    user_id = message.from_user.id
    text = message.text

    if user_id not in user_state:
        if "t.me/" in text:
            try:
                target_msg = await app.get_messages_from_link(text)
                user_state[user_id] = {"target_chat": target_msg.chat.id}
                await message.reply("✅ Target channel detected.\nNow send me the **first message link** of the source channel.")
            except:
                await message.reply("❌ Failed to extract target channel from the link.")
        else:
            await message.reply("❌ Please send a valid message link.")

    elif "first_msg_id" not in user_state[user_id]:
        if "t.me/" in text:
            try:
                msg = await app.get_messages_from_link(text)
                user_state[user_id]["source_chat"] = msg.chat.id
                user_state[user_id]["first_msg_id"] = msg.message_id
                await message.reply("✅ Got first message.\nNow send the **last message link** to define the range.")
            except:
                await message.reply("❌ Failed to extract source message.")
        else:
            await message.reply("❌ Send a valid message link.")

    elif "last_msg_id" not in user_state[user_id]:
        if "t.me/" in text:
            try:
                msg = await app.get_messages_from_link(text)
                user_state[user_id]["last_msg_id"] = msg.message_id

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
                        print(f"Failed at {msg_id}: {e}")

                await message.reply("✅ Done forwarding messages!")

                del user_state[user_id]
            except:
                await message.reply("❌ Failed to get last message.")
        else:
            await message.reply("❌ Send a valid last message link.")

keep_alive()
app.run()
