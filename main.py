import logging
import os
import shlex
import asyncio
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    PicklePersistence,
    filters,
)
from telegram.constants import ParseMode
from telegram.error import TelegramError

# Flask import - Web server ke liye (Uptimer ke liye)
try:
    from flask import Flask, request as flask_request
except ImportError:
    print("Flask library not found. Please install it: pip install Flask")
    exit()

# Set up logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- Environment Variables ---
# Render yeh variables automatically dega (PORT) ya aapko set karne honge
BOT_TOKEN = os.environ.get("BOT_TOKEN")
# Render 'RENDER_EXTERNAL_URL' naam ka variable deta hai
WEBHOOK_URL = os.environ.get("RENDER_EXTERNAL_URL") 
# Render 'PORT' naam ka variable deta hai
PORT = int(os.environ.get("PORT", 8080))

# --- Flask App (Uptimer ke liye) ---
# Yeh chota web server UptimeRobot ko "Bot zinda hai" batane ke liye hai
flask_app = Flask(__name__)
@flask_app.route('/')
def index():
    """UptimeRobot is endpoint ko ping karega"""
    return "Bot is alive and running!", 200

# --- Helper Functions ---

async def is_admin(chat_id: int, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Check karein ki bot chat mein admin hai ya nahi."""
    if not chat_id:
        return False
    try:
        bot_member = await context.bot.get_chat_member(chat_id, context.bot.id)
        return bot_member.status in ('administrator', 'creator')
    except TelegramError as e:
        logger.error(f"Error checking admin status in {chat_id}: {e}")
        if "chat not found" in str(e) or "user is not a member" in str(e) or "bot was kicked" in str(e):
             logger.warning(f"Bot chat {chat_id} mein nahi hai.")
        return False

def get_text_and_entities(update: Update):
    """LIVE message se text aur media extract karein."""
    if update.channel_post:
        msg = update.channel_post
    elif update.message:
        msg = update.message
    else:
        return None, None, None, None, None # text, entities, file_id, file_type, msg_id

    # Yahaan hum plain text/caption nikal rahe hain.
    # Is process mein original formatting (bold, italic) chali jaayegi.
    text = msg.text or msg.caption or ""
    
    # Hum entities (formatting) ko aage nahi bhej rahe hain kyunki replacement
    # ke baad unki positioning galat ho jaati hai.
    entities = [] 
    
    file_id = None
    file_type = None
    if msg.photo:
        file_id = msg.photo[-1].file_id; file_type = 'photo'
    elif msg.video:
        file_id = msg.video.file_id; file_type = 'video'
    elif msg.document:
        file_id = msg.document.file_id; file_type = 'document'
    elif msg.audio:
        file_id = msg.audio.file_id; file_type = 'audio'
    elif msg.voice:
        file_id = msg.voice.file_id; file_type = 'voice'
    elif msg.sticker:
        file_id = msg.sticker.file_id; file_type = 'sticker'
        
    return text, entities, file_id, file_type, msg.message_id

def apply_replacements(text: str, replacements: list) -> str:
    """Text par sabhi replacement rules apply karein."""
    if not text:
        return text
    modified_text = text
    # Multiple replacements
    for old, new in replacements:
        modified_text = modified_text.replace(old, new)
    return modified_text

# --- Bot Command Handlers (PTB) ---

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "👋 Hello! Main aapka Forwarder Bot hoon.\n"
        "Main *naye* messages ko replacement ke saath forward kar sakta hoon.\n"
        "Use /help to see all commands."
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Saare commands ki jaankari dein."""
    help_text = (
        "**Sabhi Commands Ki List:**\n\n"
        "**1. Setup:**\n"
        "• `/get_id`: Is chat ki ID batata hai.\n"
        "• `/set_source <channel_id>`: Source channel set karein (e.g., `-100123...`).\n"
        "• `/set_target <channel_id>`: Target channel set karein.\n"
        "• `/status`: Current source, target, aur rules dikhata hai.\n\n"
        "**2. Replacement (Sirf Naye Messages Ke Liye):**\n"
        "• `/add_replace \"old\" \"new\"`: Ek replacement rule add karein. Quotes zaroori hain.\n"
        "• `/list_replace`: Sabhi replacement rules ki list dikhata hai.\n"
        "• `/clear_replacements`: Sabhi rules ko delete karta hai.\n\n"
        "**3. Manual Forwarding:**\n"
        "• `/forward_range <start> <end>`: Purane messages ko copy karta hai.\n"
        "   ⚠️ **Note:** Yeh command sirf messages ko **COPY** karta hai, isme **REPLACEMENT NAHI HOTA**.\n\n"
        "**Kaise Kaam Karta Hai?**\n"
        "Setup poora hone ke baad, source channel mein aane wala har *naya* message automatically replace hokar target channel par bhej diya jayega."
    )
    await update.message.reply_text(help_text, parse_mode=ParseMode.MARKDOWN)

async def get_id_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    await update.message.reply_text(
        f"Is chat ki ID hai: `{chat_id}`", parse_mode=ParseMode.MARKDOWN
    )

async def set_source_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.args:
        await update.message.reply_text("Usage: /set_source <channel_id_or_username>")
        return
    chat_id_str = context.args[0]
    # Check if it's a numeric ID first
    if chat_id_str.lstrip('-').isdigit():
        chat_id = int(chat_id_str)
    else:
        chat_id = chat_id_str # Keep as username string
        
    context.bot_data['source_channel'] = chat_id
    await update.message.reply_text(f"✅ Source channel set to: {chat_id}")

async def set_target_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.args:
        await update.message.reply_text("Usage: /set_target <channel_id_or_username>")
        return
    chat_id_str = context.args[0]
    if chat_id_str.lstrip('-').isdigit():
        chat_id = int(chat_id_str)
        # Admin status check karein
        if not await is_admin(chat_id, context):
            await update.message.reply_text(f"Main {chat_id} mein admin nahi hoon. Please mujhe admin banayein.")
            return
    else:
        chat_id = chat_id_str

    context.bot_data['target_channel'] = chat_id
    await update.message.reply_text(f"✅ Target channel set to: {chat_id}")

async def add_replace_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Text replacement rule add karein."""
    try:
        command_args_text = update.message.text.split(' ', 1)
        if len(command_args_text) < 2:
            raise ValueError("No arguments provided.")
        args = shlex.split(command_args_text[1])
        if len(args) != 2:
            raise ValueError("Invalid argument count.")
        old_text, new_text = args
        
        if 'replacements' not in context.bot_data:
            context.bot_data['replacements'] = []
        context.bot_data['replacements'].append((old_text, new_text))
        
        await update.message.reply_text(f"✅ Replacement rule add ho gaya:\n`{old_text}` -> `{new_text}`", parse_mode=ParseMode.MARKDOWN)
    except Exception as e:
        logger.error(f"Error adding replace rule: {e}")
        await update.message.reply_text(f"Error: {e}\nUsage: /add_replace \"old text\" \"new text\"")

async def list_replace_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    replacements = context.bot_data.get('replacements', [])
    if not replacements:
        await update.message.reply_text("Abhi koi replacement rules set nahi hain.")
        return
    message = "Current replacement rules:\n\n"
    for i, (old, new) in enumerate(replacements, 1):
        message += f"{i}. `{old}` -> `{new}`\n"
    await update.message.reply_text(message, parse_mode=ParseMode.MARKDOWN)

async def clear_replacements_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    context.bot_data['replacements'] = []
    await update.message.reply_text("✅ Sabhi replacement rules clear kar diye gaye hain.")

async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    source = context.bot_data.get('source_channel', 'Not Set')
    target = context.bot_data.get('target_channel', 'Not Set')
    status_text = (
        f"**Bot Status**\n"
        f"Source Channel: `{source}`\n"
        f"Target Channel: `{target}`\n"
    )
    replacements = context.bot_data.get('replacements', [])
    if replacements:
        status_text += "\n**Replacements:**\n"
        for i, (old, new) in enumerate(replacements, 1):
            status_text += f"{i}. `{old}` -> `{new}`\n"
    else:
        status_text += "\nNo replacement rules."
    await update.message.reply_text(status_text, parse_mode=ParseMode.MARKDOWN)

# --- Live Message Handler (PTB) ---

async def handle_channel_post(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Naye (live) channel posts ko handle karein (Replacement ke saath)."""
    source_channel = context.bot_data.get('source_channel')
    target_channel = context.bot_data.get('target_channel')
    replacements = context.bot_data.get('replacements', [])
    if not source_channel or not target_channel:
        return
        
    chat_id = update.channel_post.chat.id
    username = update.channel_post.chat.username
    
    is_from_source = False
    if isinstance(source_channel, int):
        is_from_source = (chat_id == source_channel)
    elif isinstance(source_channel, str):
        is_from_source = (str(chat_id) == source_channel) or (username and str(username).lower() == source_channel.lstrip('@').lower())

    if not is_from_source:
        return

    try:
        # Hum entities=entities nahi bhej rahe hain, taaki formatting plain ho jaaye
        text, _, file_id, file_type, msg_id = get_text_and_entities(update)
        
        # Naye messages par replacement apply karein
        modified_text = apply_replacements(text, replacements)
        
        if file_type == 'photo':
            await context.bot.send_photo(chat_id=target_channel, photo=file_id, caption=modified_text)
        elif file_type == 'video':
            await context.bot.send_video(chat_id=target_channel, video=file_id, caption=modified_text)
        elif file_type == 'document':
            await context.bot.send_document(chat_id=target_channel, document=file_id, caption=modified_text)
        elif file_type == 'audio':
            await context.bot.send_audio(chat_id=target_channel, audio=file_id, caption=modified_text)
        elif file_type == 'voice':
             await context.bot.send_voice(chat_id=target_channel, voice=file_id, caption=modified_text)
        elif file_type == 'sticker':
            await context.bot.send_sticker(chat_id=target_channel, sticker=file_id)
        elif modified_text: # Sirf text message
            await context.bot.send_message(chat_id=target_channel, text=modified_text)
        elif text and not modified_text: # Agar text tha aur replacement ke baad empty ho gaya
             logger.info(f"Live msg {msg_id} replacement ke baad empty hai. Skip kar raha hoon.")
        else: # Na text, na media
            logger.info(f"Live msg {msg_id} mein text ya media nahi hai. Skip kar raha hoon.")
        
        logger.info(f"Live message {msg_id} ko {source_channel} se {target_channel} forward kiya.")
    except Exception as e:
        logger.error(f"Live message {update.channel_post.message_id} forward karne mein fail hua: {e}")

# --- Range Forward Handler (PTB) ---

async def forward_range_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Purane messages ko copy karein (REPLACEMENT KE BINA)."""
    
    source_channel = context.bot_data.get('source_channel')
    target_channel = context.bot_data.get('target_channel')

    if not source_channel or not target_channel:
        await update.message.reply_text("Pehle source aur target channels set karein.")
        return
        
    if len(context.args) != 2:
        await update.message.reply_text("Usage: /forward_range <start_message_id> <end_message_id>")
        return

    try:
        start_id = int(context.args[0])
        end_id = int(context.args[1])
        if start_id > end_id:
            await update.message.reply_text("Start ID hamesha End ID se chota hona chahiye.")
            return

        await update.message.reply_text(f"Messages {start_id} se {end_id} tak copy karna shuru kar raha hoon... (Bina replacement ke)")

        count_success = 0
        count_fail = 0
        
        for message_id in range(start_id, end_id + 1):
            try:
                # Sirf copy karein. Replacement possible nahi hai.
                await context.bot.copy_message(
                    chat_id=target_channel,
                    from_chat_id=source_channel,
                    message_id=message_id
                )
                count_success += 1
                await asyncio.sleep(1.2) # Telegram rate limits se bachne ke liye thoda pause
            except Exception as e:
                logger.error(f"Message {message_id} copy karne mein fail hua: {e}")
                count_fail += 1
                await asyncio.sleep(1)

        await update.message.reply_text(
            f"✅ Batch copy complete!\n"
            f"Successfully copied: {count_success} messages\n"
            f"Failed to copy: {count_fail} messages"
        )

    except ValueError:
        await update.message.reply_text("Message IDs numbers hone chahiye. Usage: /forward_range <start> <end>")
    except Exception as e:
        await update.message.reply_text(f"Ek error aaya: {e}")
        logger.error(f"Error in forward_range: {e}")

# --- Main Application Setup (PTB + Flask) ---

async def setup_bot():
    """Bot application ko setup karein."""
    if not BOT_TOKEN:
        logger.critical("BOT_TOKEN environment variable nahi mila!")
        raise ValueError("BOT_TOKEN environment variable nahi mila")
    if not WEBHOOK_URL:
        logger.critical("RENDER_EXTERNAL_URL (WEBHOOK_URL) environment variable nahi mila")
        raise ValueError("RENDER_EXTERNAL_URL (WEBHOOK_URL) environment variable nahi mila")

    persistence = PicklePersistence(filepath="bot_data.pickle")
    application = (
        Application.builder()
        .token(BOT_TOKEN)
        .persistence(persistence)
        .build()
    )

    # Command handlers add karein
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("get_id", get_id_command))
    application.add_handler(CommandHandler("set_source", set_source_command))
    application.add_handler(CommandHandler("set_target", set_target_command))
    application.add_handler(CommandHandler("add_replace", add_replace_command))
    application.add_handler(CommandHandler("list_replace", list_replace_command))
    application.add_handler(CommandHandler("clear_replacements", clear_replacements_command))
    application.add_handler(CommandHandler("status", status_command))
    application.add_handler(CommandHandler("forward_range", forward_range_command))

    # Naye messages ke liye handler
    application.add_handler(MessageHandler(filters.ChatType.CHANNEL, handle_channel_post))

    # Webhook set karein
    try:
        await application.bot.set_webhook(
            url=f"{WEBHOOK_URL}/{BOT_TOKEN}",
            allowed_updates=Update.ALL_TYPES
        )
        logger.info(f"Webhook ko {WEBHOOK_URL} par set kar diya gaya hai")
    except Exception as e:
        logger.error(f"Webhook set karne mein fail hua: {e}")
        return None, None

    return application, application.bot

# Flask server ko Telegram app ke saath jodein
async def run_flask(application):
    @flask_app.route(f'/{BOT_TOKEN}', methods=['POST'])
    async def webhook():
        """Telegram se updates handle karein"""
        try:
            update_data = flask_request.get_json()
            update = Update.de_json(data=update_data, bot=application.bot)
            await application.process_update(update)
            return 'ok', 200
        except Exception as e:
            logger.error(f"Webhook handler mein error: {e}")
            return 'error', 500

    logger.info("Flask server start ho raha hai...")
    # '0.0.0.0' par host karein taaki Render ise access kar sake
    # debug=False production ke liye zaroori hai
    flask_app.run(host='0.0.0.0', port=PORT, debug=False)

async def main():
    application, bot = await setup_bot()
    if application:
        await run_flask(application)

if __name__ == "__main__":
    # Python 3.7+ ke liye asyncio.run() best tareeka hai
    asyncio.run(main())
