# bot.py
import os
import json
import asyncio
import logging
from typing import List

from pyrogram import Client, filters
from pyrogram.types import Message
from pyrogram.errors import FloodWait, RPCError

from keep_alive import run_web  # async function to start keep-alive webserver

# ---------------- Config / Logging ----------------
logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
log = logging.getLogger("forward-bot")

API_ID = int(os.environ.get("API_ID", "0"))
API_HASH = os.environ.get("API_HASH")
BOT_TOKEN = os.environ.get("BOT_TOKEN")
OWNER_ID = int(os.environ.get("OWNER_ID", "0"))

# file to persist destinations & source
DATA_FILE = "destinations.json"

# Forwarding behavior config (tweak if you want)
PER_TARGET_DELAY = 0.8        # seconds between copying to each destination
BATCH_SIZE = 10               # after this many messages, take a longer break
BATCH_SLEEP = 6               # seconds to sleep after each batch
RETRY_DELAY = 3               # seconds to wait before retrying a failed message
MAX_RETRIES = 3               # max retries per copy

# ---------------- Storage helpers ----------------
def load_data():
    try:
        with open(DATA_FILE, "r") as f:
            data = json.load(f)
            # ensure keys
            return {
                "source": data.get("source"),
                "destinations": data.get("destinations", [])
            }
    except FileNotFoundError:
        return {"source": None, "destinations": []}
    except Exception as e:
        log.exception("Failed to load data.json, starting fresh")
        return {"source": None, "destinations": []}

def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=2)

data = load_data()

# ---------------- Pyrogram client ----------------
app = Client(
    "multi-forward-bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
    workdir="."
)

# ---------------- Utility ----------------
def is_owner(user_id: int) -> bool:
    return int(user_id) == OWNER_ID

def format_dest_list(dest_list: List[int]) -> str:
    if not dest_list:
        return "No destinations set."
    return "\n".join(str(d) for d in dest_list)

# ---------------- Commands ----------------
@app.on_message(filters.command("start"))
async def cmd_start(client, message: Message):
    await message.reply_text(
        "👋 Multi-forward Bot is running.\n\n"
        "Owner-only commands:\n"
        "/setsource <chat_id> - set source channel/group\n"
        "/adddest <chat_id> - add a destination\n"
        "/rmdest <chat_id> - remove a destination\n"
        "/listdest - list destinations\n"
        "/clear - clear all destinations\n"
        "/forward <start_id> <end_id> - forward range to all destinations\n\n"
        "Example:\n"
        "/setsource -1001234567890\n"
        "/adddest -1009876543210\n"
        "/forward 1 200\n\n"
        "Tip: For private channels (/c/ links), convert as -100<id> (e.g. link has 2867606311 -> -1002867606311)."
    )

@app.on_message(filters.command("setsource"))
async def cmd_setsource(client, message: Message):
    if not is_owner(message.from_user.id):
        return await message.reply_text("⛔ Only owner can set source.")
    parts = message.text.split()
    if len(parts) != 2:
        return await message.reply_text("Usage: /setsource <chat_id_or_username>")
    source = parts[1].strip()
    # try cast to int if numeric
    try:
        source_val = int(source)
    except:
        source_val = source  # username string
    data["source"] = source_val
    save_data(data)
    await message.reply_text(f"✅ Source set to: `{source_val}`", quote=True)

@app.on_message(filters.command("adddest"))
async def cmd_adddest(client, message: Message):
    if not is_owner(message.from_user.id):
        return await message.reply_text("⛔ Only owner can add destinations.")
    parts = message.text.split()
    if len(parts) != 2:
        return await message.reply_text("Usage: /adddest <chat_id_or_username>")
    dest = parts[1].strip()
    try:
        dest_val = int(dest)
    except:
        dest_val = dest
    if dest_val in data["destinations"]:
        return await message.reply_text("⚠️ Destination already exists.")
    data["destinations"].append(dest_val)
    save_data(data)
    await message.reply_text(f"✅ Added destination: `{dest_val}`", quote=True)

@app.on_message(filters.command("rmdest"))
async def cmd_rmdest(client, message: Message):
    if not is_owner(message.from_user.id):
        return await message.reply_text("⛔ Only owner can remove destinations.")
    parts = message.text.split()
    if len(parts) != 2:
        return await message.reply_text("Usage: /rmdest <chat_id_or_username>")
    dest = parts[1].strip()
    try:
        dest_val = int(dest)
    except:
        dest_val = dest
    if dest_val not in data["destinations"]:
        return await message.reply_text("⚠️ Destination not found.")
    data["destinations"].remove(dest_val)
    save_data(data)
    await message.reply_text(f"✅ Removed destination: `{dest_val}`", quote=True)

@app.on_message(filters.command("listdest"))
async def cmd_listdest(client, message: Message):
    if not is_owner(message.from_user.id):
        return await message.reply_text("⛔ Only owner can view destinations.")
    text = "📌 Destinations:\n" + (format_dest_list(data["destinations"]) or "No destinations.")
    await message.reply_text(text)

@app.on_message(filters.command("clear"))
async def cmd_clear(client, message: Message):
    if not is_owner(message.from_user.id):
        return await message.reply_text("⛔ Only owner can clear destinations.")
    data["destinations"] = []
    save_data(data)
    await message.reply_text("🧹 All destinations cleared.")

@app.on_message(filters.command("status"))
async def cmd_status(client, message: Message):
    if not is_owner(message.from_user.id):
        return await message.reply_text("⛔ Only owner can view status.")
    src = data.get("source") or "Not set"
    dests = data.get("destinations", [])
    await message.reply_text(f"🔎 Status:\nSource: `{src}`\nDestinations: {len(dests)}")

# ---------------- Forwarding logic ----------------
async def copy_message_with_retries(client: Client, from_chat, message_id, to_chat):
    """Copy a single message from from_chat:message_id to to_chat with retries and flood handling."""
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            await client.copy_message(chat_id=to_chat, from_chat_id=from_chat, message_id=message_id)
            return True
        except FloodWait as fw:
            wait = int(fw.x) if hasattr(fw, "x") else fw.value
            log_msg = f"FloodWait {wait}s on copy to {to_chat} — sleeping..."
            log.warning(log_msg)
            await asyncio.sleep(wait + 1)
        except RPCError as rpc_e:
            # some RPC errors may be temporary
            log.warning(f"RPCError copying msg {message_id} to {to_chat}: {rpc_e} (attempt {attempt})")
            await asyncio.sleep(RETRY_DELAY)
        except Exception as e:
            log.exception(f"Unexpected error copying msg {message_id} to {to_chat}: {e}")
            await asyncio.sleep(RETRY_DELAY)
    return False

@app.on_message(filters.command("forward") & filters.user(OWNER_ID))
async def cmd_forward(client: Client, message: Message):
    """
    Usage:
    /forward <start_id> <end_id>
    The source must be set with /setsource and destinations with /adddest.
    """
    if not data.get("source"):
        return await message.reply_text("❌ Source not set. Use /setsource <chat_id_or_username>")

    if not data.get("destinations"):
        return await message.reply_text("❌ No destinations set. Use /adddest <chat_id_or_username>")

    parts = message.text.split()
    if len(parts) != 3:
        return await message.reply_text("Usage: /forward <start_id> <end_id>")

    try:
        start_id = int(parts[1])
        end_id = int(parts[2])
    except ValueError:
        return await message.reply_text("❌ start_id and end_id must be integers")

    src = data["source"]
    dests = list(data["destinations"])

    total_msgs = max(0, end_id - start_id + 1)
    await message.reply_text(f"🚀 Forwarding {total_msgs} messages from `{src}` to {len(dests)} destinations. This can take time...")

    forwarded_count = 0
    msg_index = 0
    for msg_id in range(start_id, end_id + 1):
        msg_index += 1
        # fetch message once
        try:
            msg = await client.get_messages(src, msg_id)
            if not msg:
                log.warning(f"Message {msg_id} not found at source {src}. Skipping.")
                continue
        except FloodWait as fw:
            wait = int(fw.x) if hasattr(fw, "x") else fw.value
            log.warning(f"FloodWait while get_messages: sleeping {wait}s")
            await asyncio.sleep(wait + 1)
            # try again for same msg_id
            try:
                msg = await client.get_messages(src, msg_id)
            except Exception as e:
                log.exception(f"Failed to fetch msg {msg_id} after flood-wait: {e}")
                continue
        except Exception as e:
            log.exception(f"Failed to fetch msg {msg_id}: {e}")
            continue

        # send to each destination
        for dest in dests:
            success = await copy_message_with_retries(client, src, msg_id, dest)
            if not success:
                log.warning(f"Failed to copy message {msg_id} to {dest} after retries. Continuing.")
            await asyncio.sleep(PER_TARGET_DELAY)

        forwarded_count += 1

        # batch sleep for flood control
        if forwarded_count % BATCH_SIZE == 0:
            log.info(f"Batch {forwarded_count} done. Sleeping {BATCH_SLEEP}s...")
            await asyncio.sleep(BATCH_SLEEP)

    await message.reply_text(f"✅ Forwarding complete. Messages attempted: {total_msgs}, messages fetched+sent: {forwarded_count}")

# ---------------- Program entry ----------------
async def main():
    # start web keep-alive server (non-blocking)
    asyncio.create_task(run_web())  # run_web is async and will run in same loop
    # start pyrogram client
    await app.start()
    log.info("Pyrogram client started. Bot is up.")
    # Idle - keep the bot running until stopped
    await app.idle()
    # on shutdown
    await app.stop()
    log.info("Pyrogram client stopped.")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        log.info("Stopping by KeyboardInterrupt")
