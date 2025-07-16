from pyrogram import Client, filters, enums
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.errors import FloodWait
from keep_alive import keep_alive
import os
import asyncio
import re
import time

API_ID = int(os.environ.get("API_ID"))
API_HASH = os.environ.get("API_HASH")
BOT_TOKEN = os.environ.get("BOT_TOKEN")
OWNER_ID = int(os.environ.get("OWNER_ID"))

app = Client("forward_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

user_state = {}

# ... (keep all previous functions unchanged until start_forwarding)

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
    last_update = 0
    
    status_msg = await message.reply(f"⏳ Starting to forward {total_messages} messages... (0%)")
    
    # Process messages individually with proper rate limiting
    for msg_id in range(first, last + 1):
        try:
            # Get message with retry logic
            msg = None
            for attempt in range(3):
                try:
                    msg = await app.get_messages(source, msg_id)
                    break
                except FloodWait as e:
                    wait_time = e.value + 2
                    await status_msg.edit(f"⏳ Flood control. Waiting {wait_time} seconds...")
                    await asyncio.sleep(wait_time)
                except Exception as e:
                    print(f"Error getting message {msg_id} (attempt {attempt+1}): {e}")
                    await asyncio.sleep(3)
            
            if not msg or not msg.id:
                failed_messages.append(msg_id)
                continue
            
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
            
            # Update progress max every 15 seconds or 5% change
            current_time = time.time()
            progress = int(total_forwarded / total_messages * 100)
            
            if current_time - last_update > 15 or progress % 5 == 0:
                try:
                    await status_msg.edit(f"⏳ Forwarding... {progress}% ({total_forwarded}/{total_messages})")
                    last_update = current_time
                except:
                    pass
            
            # Dynamic sleep based on message type
            sleep_time = 1.5  # Base sleep time
            if msg.media:
                sleep_time = 3.0  # Longer sleep for media messages
            elif msg.text and len(msg.text) > 1000:
                sleep_time = 2.5  # Longer sleep for long text
            
            await asyncio.sleep(sleep_time)
        
        except FloodWait as e:
            wait_time = e.value + 2
            await status_msg.edit(f"⏳ Flood control. Waiting {wait_time} seconds...")
            await asyncio.sleep(wait_time)
            
            # Retry the same message after wait
            try:
                msg = await app.get_messages(source, msg_id)
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
            except Exception:
                failed_messages.append(msg_id)
        
        except Exception as e:
            print(f"Error forwarding {msg_id}: {e}")
            failed_messages.append(msg_id)
            await asyncio.sleep(1)
    
    # Final report
    report = f"✅ Forwarded {total_forwarded}/{total_messages} messages successfully!"
    if failed_messages:
        report += f"\n\n❌ Failed messages: {len(failed_messages)}\nIDs: {', '.join(map(str, failed_messages[:10]))}" + \
                 ("..." if len(failed_messages) > 10 else "")
    
    report += f"\n\nTarget: `{target}`\nReplacements applied: {len(replacements)}"
    
    try:
        await status_msg.delete()
    except:
        pass
    await message.reply(report, parse_mode=enums.ParseMode.MARKDOWN)
    del user_state[uid]

keep_alive()
app.run()
