from pyrogram import Client, filters, enums
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from keep_alive import keep_alive
import os
import asyncio
import re
import time

# Fixed environment variable syntax
API_ID = int(os.environ.get("API_ID"))
API_HASH = os.environ.get("API_HASH")
BOT_TOKEN = os.environ.get("BOT_TOKEN")
OWNER_ID = int(os.environ.get("OWNER_ID"))

app = Client("forward_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

user_state = {}

@app.on_message(filters.command("start") & filters.user(OWNER_ID))
async def start(client, message):
    await message.reply(
        "👋 **Forward Bot Instructions**\n\n"
        "1. Forward a message from **target channel**\n"
        "2. Forward **first message** from source\n"
        "3. Forward **last message** from source\n"
        "4. Configure replacements (optional)\n\n"
        "Use /replace to configure text replacements\n"
        "Use /reset to clear current state",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("Set Replacements", callback_data="set_replacements")]
        ])
    )

@app.on_message(filters.command("reset") & filters.user(OWNER_ID))
async def reset(client, message):
    user_state.pop(message.from_user.id, None)
    await message.reply("🔄 Reset done. Start again by forwarding target message.")

@app.on_message(filters.command("replace") & filters.user(OWNER_ID))
async def replace_command(client, message):
    uid = message.from_user.id
    if uid not in user_state:
        return await message.reply("❌ Start the process first with /start")
    
    user_state[uid]["waiting_for_replacement"] = True
    await message.reply(
        "🔧 Send replacement rules in this format:\n\n"
        "`pattern | replacement`\n\n"
        "Example:\n"
        "`old text | new text`\n"
        "`https://old\\.com | https://new.com`\n\n"
        "Send /done when finished",
        parse_mode=enums.ParseMode.MARKDOWN
    )

@app.on_callback_query(filters.user(OWNER_ID))
async def callback_handler(client, query):
    uid = query.from_user.id
    if query.data == "set_replacements":
        if uid not in user_state:
            await query.answer("Start the process first!", show_alert=True)
            return
        
        user_state[uid]["waiting_for_replacement"] = True
        await query.message.edit(
            "🔧 Send replacement rules in this format:\n\n"
            "`pattern | replacement`\n\n"
            "Example:\n"
            "`old text | new text`\n"
            "`https://old\\.com | https://new.com`\n\n"
            "Send /done when finished",
            parse_mode=enums.ParseMode.MARKDOWN
        )
    elif query.data == "start_forwarding":
        state = user_state.get(uid)
        if not state:
            await query.answer("Session expired. Start again.", show_alert=True)
            return
        
        state["waiting_for_replacement"] = False
        await query.message.edit("✅ Starting forwarding without replacements...")
        await start_forwarding(uid, query.message)

@app.on_message(filters.forwarded & filters.user(OWNER_ID))
async def handle_forward(client, message: Message):
    uid = message.from_user.id

    if not message.forward_from_chat:
        return await message.reply("❌ Not a valid forwarded message.")

    # Initialize user state if needed
    if uid not in user_state:
        user_state[uid] = {
            "target_chat": message.forward_from_chat.id,
            "replacements": []
        }
        return await message.reply("✅ Target chat saved. Now forward the FIRST source message.")

    state = user_state[uid]
    
    if "source_chat" not in state:
        state["source_chat"] = message.forward_from_chat.id
        state["first_msg_id"] = message.forward_from_message_id
        return await message.reply("✅ First message saved. Now forward the LAST source message.")

    if "last_msg_id" not in state:
        state["last_msg_id"] = message.forward_from_message_id
        state["waiting_for_replacement"] = True
        await message.reply(
            "✅ Last message saved. Configure text replacements:\n\n"
            "Send replacement rules in format:\n"
            "`pattern | replacement`\n\n"
            "Or send /done to start forwarding",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("Skip Replacements", callback_data="start_forwarding")]
            ]),
            parse_mode=enums.ParseMode.MARKDOWN
        )

@app.on_message(filters.text & filters.user(OWNER_ID) & filters.private)
async def handle_replacement(client, message: Message):
    uid = message.from_user.id
    if uid not in user_state:
        return
    
    state = user_state[uid]
    if not state.get("waiting_for_replacement"):
        return

    text = message.text.strip()
    
    if text.lower() == "/done":
        state["waiting_for_replacement"] = False
        await message.reply("✅ Finished adding replacements. Starting forwarding...")
        await start_forwarding(uid, message)
        return

    if " | " not in text:
        return await message.reply("❌ Invalid format. Use: `pattern | replacement`", parse_mode=enums.ParseMode.MARKDOWN)

    pattern, replacement = text.split(" | ", 1)
    
    try:
        # Test regex pattern
        re.compile(pattern)
        state["replacements"].append((pattern, replacement))
        await message.reply(f"✅ Added replacement:\n\n`{pattern}` → `{replacement}`", parse_mode=enums.ParseMode.MARKDOWN)
    except re.error as e:
        await message.reply(f"❌ Invalid regex pattern: {e}. Please try again.")

async def apply_replacements(text, replacements):
    if not text or not replacements:
        return text
    
    for pattern, replacement in replacements:
        try:
            text = re.sub(pattern, replacement, text)
        except Exception:
            continue
    return text

async def start_forwarding(uid, message: Message):
    state = user_state.get(uid)
    if not state:
        return
    
    source = state["source_chat"]
    target = state["target_chat"]
    first = state["first_msg_id"]
    last = state["last_msg_id"]
    replacements = state["replacements"]
    
    total_messages = last - first + 1
    total_forwarded = 0
    failed_messages = []
    
    status_msg = await message.reply(f"⏳ Starting to forward {total_messages} messages... (0%)")

    # Batch processing (100 messages per request)
    batch_size = 100
    for offset in range(0, total_messages, batch_size):
        batch_start = first + offset
        batch_end = min(first + offset + batch_size, last + 1)
        batch_ids = list(range(batch_start, batch_end))
        
        try:
            messages = await app.get_messages(source, batch_ids)
        except Exception as e:
            await message.reply(f"⚠️ Error getting messages: {e}")
            continue

        for msg in messages:
            if not msg:
                failed_messages.append(batch_start + len(failed_messages))
                continue
            
            try:
                # Apply text replacements
                if replacements:
                    if msg.text:
                        new_text = await apply_replacements(msg.text, replacements)
                        await app.send_message(target, new_text)
                    elif msg.caption:
                        new_caption = await apply_replacements(msg.caption, replacements)
                        await msg.copy(target, caption=new_caption)
                    else:
                        await msg.copy(target)
                else:
                    await msg.copy(target)
                
                total_forwarded += 1
                
                # Update progress every 10 messages or 5%
                if total_forwarded % 10 == 0 or total_forwarded % max(1, total_messages//20) == 0:
                    progress = int(total_forwarded / total_messages * 100)
                    await status_msg.edit(f"⏳ Forwarding... {progress}% ({total_forwarded}/{total_messages})")
            
            except Exception as e:
                print(f"Error forwarding {msg.id}: {e}")
                failed_messages.append(msg.id)
        
        # Avoid flooding and respect Telegram limits
        await asyncio.sleep(5)
    
    # Final report
    report = f"✅ Forwarded {total_forwarded}/{total_messages} messages successfully!"
    if failed_messages:
        report += f"\n\n❌ Failed messages: {len(failed_messages)}\nIDs: {', '.join(map(str, failed_messages[:10]))}" + \
                 ("..." if len(failed_messages) > 10 else "")
    
    report += f"\n\nTarget: `{target}`\nReplacements applied: {len(replacements)}"
    
    await status_msg.delete()
    await message.reply(report, parse_mode=enums.ParseMode.MARKDOWN)
    del user_state[uid]

keep_alive()
app.run()
