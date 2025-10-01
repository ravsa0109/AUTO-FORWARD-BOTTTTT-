import os
import asyncio
from pyrogram import Client, filters

API_ID = int(os.environ.get("API_ID"))
API_HASH = os.environ.get("API_HASH")
BOT_TOKEN = os.environ.get("BOT_TOKEN")
OWNER_ID = int(os.environ.get("OWNER_ID"))

app = Client(
    "forward-bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)

# Forward command
@app.on_message(filters.command("forward") & filters.user(OWNER_ID))
async def forward_messages(client, message):
    try:
        # Command format: /forward source_id target1,target2 target_msg_start-target_msg_end
        args = message.text.split(" ")

        if len(args) < 4:
            await message.reply_text(
                "❌ Wrong format.\n\nUsage:\n`/forward <source_chat_id> <target_chat_id1,target_chat_id2,...> <start_msg_id>-<end_msg_id>`"
            )
            return

        source_chat = int(args[1]) if args[1].lstrip("-").isdigit() else args[1]
        target_chats = [int(t) if t.lstrip("-").isdigit() else t for t in args[2].split(",")]
        msg_range = args[3].split("-")

        start_id = int(msg_range[0])
        end_id = int(msg_range[1])

        sent_count = 0
        for msg_id in range(start_id, end_id + 1):
            try:
                msg = await client.get_messages(source_chat, msg_id)

                for target in target_chats:
                    await msg.copy(target)

                sent_count += 1

                # हर 10 messages के बाद 6 sec का gap
                if sent_count % 10 == 0:
                    await asyncio.sleep(6)

            except Exception as e:
                await message.reply_text(f"⚠️ Error at message {msg_id}: {e}")
                continue

        await message.reply_text(f"✅ Forwarded {sent_count} messages from {source_chat} to {len(target_chats)} targets.")

    except Exception as e:
        await message.reply_text(f"❌ Error: {e}")


@app.on_message(filters.command("start"))
async def start(client, message):
    if message.from_user.id == OWNER_ID:
        await message.reply_text("👋 Bot is running!\nUse /forward command to start forwarding.")
    else:
        await message.reply_text("❌ You are not authorized to use this bot.")

app.run()
