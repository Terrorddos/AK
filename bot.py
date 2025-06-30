import logging
import sqlite3
import time
from datetime import datetime, timedelta
from telegram import Update, ChatPermissions, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
    CallbackQueryHandler
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('bot_logs.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Database setup
def init_db():
    conn = sqlite3.connect('bot_db.sqlite')
    cursor = conn.cursor()
    
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS approved_channels (
        channel_id TEXT PRIMARY KEY,
        added_by INTEGER,
        date_added TEXT
    )''')
    
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS channel_admins (
        channel_id TEXT,
        user_id INTEGER,
        PRIMARY KEY (channel_id, user_id)
    )''')
    
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS muted_users (
        user_id INTEGER,
        chat_id TEXT,
        muted_until TEXT,
        muted_by INTEGER,
        mute_message_id INTEGER,
        mute_reason TEXT,
        PRIMARY KEY (user_id, chat_id)
    )''')
    
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS command_usage (
        user_id INTEGER,
        timestamp TEXT,
        count INTEGER DEFAULT 1,
        PRIMARY KEY (user_id)
    )''')
    
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS filtered_words (
        channel_id TEXT,
        word TEXT,
        added_by INTEGER,
        date_added TEXT,
        PRIMARY KEY (channel_id, word)
    )''')
    
    conn.commit()
    conn.close()

def execute_db(query, params=(), fetch=False):
    conn = sqlite3.connect('bot_db.sqlite')
    cursor = conn.cursor()
    cursor.execute(query, params)
    if fetch:
        result = cursor.fetchall()
    else:
        result = None
    conn.commit()
    conn.close()
    return result

# Configuration
DEVELOPER_ID = 1760943918
DEVELOPER_USERNAME = "@ABHISHEEK163"
MUTE_DURATION_MINUTES = 3
BOT_USERNAME = "@LinkRemoverT_bot"

# Spam protection configuration
SPAM_PROTECTION = {
    'MAX_COMMANDS': 5,
    'COOLDOWN': 60,
    'ADMIN_LIMIT': 10
}

BOT_ART = """
✨━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━✨
       𝓜𝓸𝓭𝓮𝓻𝓪𝓽𝓲𝓸𝓷 𝓑𝓸𝓽
✨━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━✨
"""

# Helper functions
async def is_admin_or_owner(chat_id: str, user_id: int, context: ContextTypes.DEFAULT_TYPE) -> bool:
    try:
        chat_member = await context.bot.get_chat_member(chat_id, user_id)
        return chat_member.status in ['administrator', 'creator']
    except Exception as e:
        logger.error(f"Error checking admin status: {e}")
        return False

async def is_developer(user_id: int) -> bool:
    return user_id == DEVELOPER_ID

async def check_spam(user_id: int, is_admin: bool = False) -> bool:
    """Check if user is spamming commands"""
    now = datetime.now().isoformat()
    max_commands = SPAM_PROTECTION['ADMIN_LIMIT'] if is_admin else SPAM_PROTECTION['MAX_COMMANDS']
    
    usage = execute_db(
        "SELECT timestamp, count FROM command_usage WHERE user_id = ?",
        (user_id,),
        fetch=True
    )
    
    if usage:
        last_time = datetime.fromisoformat(usage[0][0])
        count = usage[0][1]
        time_diff = (datetime.now() - last_time).total_seconds()
        
        if time_diff < SPAM_PROTECTION['COOLDOWN'] and count >= max_commands:
            return True
        
        if time_diff < SPAM_PROTECTION['COOLDOWN']:
            execute_db(
                "UPDATE command_usage SET count = count + 1 WHERE user_id = ?",
                (user_id,)
            )
        else:
            execute_db(
                "UPDATE command_usage SET count = 1, timestamp = ? WHERE user_id = ?",
                (now, user_id)
            )
    else:
        execute_db(
            "INSERT INTO command_usage (user_id, timestamp) VALUES (?, ?)",
            (user_id, now)
        )
    
    return False

def spam_protected(handler):
    """Decorator for spam protection"""
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not update.effective_user:
            return
        
        user_id = update.effective_user.id
        is_admin = await is_admin_or_owner(str(update.effective_chat.id), user_id, context) if update.effective_chat else False
        
        if await check_spam(user_id, is_admin):
            warning_msg = "⚠️ You're sending commands too fast. Please wait a minute before trying again."
            if update.message:
                await update.message.reply_text(warning_msg)
            return
        
        return await handler(update, context)
    return wrapper

# Command handlers
@spam_protected
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    welcome_msg = f"""
{BOT_ART}
👋 Hello! I'm an advanced moderation bot.

🔹 <b>Features:</b>
• Auto-link removal
• Custom word filtering
• Admin controls
• Mute management

🔹 <b>To add me to your channel:</b>
1. Add me as admin
2. Contact {DEVELOPER_USERNAME} for approval
3. Use /addwords to set filtered words

⚙️ Use /help for available commands
"""
    # Add "Add to Group" button
    keyboard = [
        [InlineKeyboardButton(
            "➕ Add to Group", 
            url=f"https://t.me/ABHISHEEK163"
        )]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        welcome_msg, 
        parse_mode='HTML',
        reply_markup=reply_markup
    )

@spam_protected
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_user:
        return
    
    user_id = update.effective_user.id
    
    if await is_developer(user_id):
        help_text = f"""
{BOT_ART}
🛠 <b>Developer Commands</b>:

• /add - Approve new channel
• /channel - List approved channels
• /stats - Show bot statistics
• /broadcast - Send message to all channels

👮 <b>Admin Commands</b>:
• /addwords - Add filtered words
• /removeword - Remove filtered word
• /listwords - List filtered words
• /help - Show this help message
• /alive - Check bot status
"""
    else:
        help_text = f"""
{BOT_ART}
🛠 <b>Admin Commands</b>:

• /addwords word1 word2 - Add filtered words
• /removeword word - Remove filtered word
• /listwords - List filtered words
• /help - Show this help message
• /alive - Check bot status
• /stats - Show channel statistics
"""
    
    await update.message.reply_text(help_text, parse_mode='HTML')

@spam_protected
async def add_channel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Developer command to approve a new channel."""
    if not await is_developer(update.effective_user.id):
        await update.message.reply_text("❌ Only the developer can use this command!")
        return
    
    if not context.args:
        await update.message.reply_text("Usage: /add <channel_id>")
        return
    
    channel_id = context.args[0]
    
    if not (channel_id.startswith('@') or channel_id.startswith('-100')):
        await update.message.reply_text("❌ Invalid channel ID format. Must start with @ or -100")
        return
    
    existing = execute_db(
        "SELECT 1 FROM approved_channels WHERE channel_id = ?",
        (channel_id,),
        fetch=True
    )
    
    if existing:
        await update.message.reply_text(f"ℹ️ Channel {channel_id} is already approved.")
    else:
        execute_db(
            "INSERT INTO approved_channels VALUES (?, ?, datetime('now'))",
            (channel_id, update.effective_user.id)
        )
        await update.message.reply_text(f"✅ Channel {channel_id} has been approved!")

@spam_protected
async def list_channels(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """List all approved channels (developer only)."""
    if not await is_developer(update.effective_user.id):
        await update.message.reply_text("❌ Only the developer can use this command!")
        return
    
    channels = execute_db(
        "SELECT channel_id FROM approved_channels ORDER BY date_added",
        fetch=True
    )
    
    if not channels:
        await update.message.reply_text("ℹ️ No channels approved yet.")
    else:
        channels_list = "\n".join([channel[0] for channel in channels])
        await update.message.reply_text(f"📋 Approved channels:\n{channels_list}")

@spam_protected
async def alive(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Check bot status with appropriate information level."""
    uptime = timedelta(seconds=time.time() - context.bot_data.get('start_time', time.time()))
    
    if await is_developer(update.effective_user.id):
        channel_count = len(execute_db("SELECT channel_id FROM approved_channels", fetch=True))
        muted_users = len(execute_db("SELECT user_id FROM muted_users", fetch=True))
        
        status_msg = f"""
{BOT_ART}
🤖 <b>Bot Status</b>

🟢 <b>Online</b>
⏱ <b>Uptime:</b> {str(uptime).split('.')[0]}
📊 <b>Channels:</b> {channel_count}
🔇 <b>Muted Users:</b> {muted_users}

🧑‍💻 <b>Developer:</b> {DEVELOPER_USERNAME}
📅 <b>Last Check:</b> {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
"""
    else:
        status_msg = f"""
{BOT_ART}
🤖 <b>Bot Status</b>

🟢 <b>Online</b>
⏱ <b>Uptime:</b> {str(uptime).split('.')[0]}

📅 <b>Last Check:</b> {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
"""
    await update.message.reply_text(status_msg, parse_mode='HTML')

@spam_protected
async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show statistics for the current channel."""
    if not update.effective_chat or not update.effective_user:
        return
    
    chat_id = str(update.effective_chat.id)
    user_id = update.effective_user.id
    
    if not await is_admin_or_owner(chat_id, user_id, context) and not await is_developer(user_id):
        await update.message.reply_text("❌ Only admins can view statistics!")
        return
    
    muted_users = execute_db(
        "SELECT user_id FROM muted_users WHERE chat_id = ?",
        (chat_id,),
        fetch=True
    )
    filtered_words = execute_db(
        "SELECT word FROM filtered_words WHERE channel_id = ?",
        (chat_id,),
        fetch=True
    )
    
    stats_msg = f"""
{BOT_ART}
📊 <b>Channel Statistics</b>

🔇 <b>Currently Muted Users:</b> {len(muted_users)}
📝 <b>Filtered Words:</b> {len(filtered_words)}

📅 <b>Last Updated:</b> {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
"""
    await update.message.reply_text(stats_msg, parse_mode='HTML')

@spam_protected
async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Developer command to broadcast message to all channels"""
    if not await is_developer(update.effective_user.id):
        await update.message.reply_text("❌ Only the developer can use this command!")
        return
    
    if not context.args:
        await update.message.reply_text("Usage: /broadcast <message>")
        return
    
    message = ' '.join(context.args)
    channels = execute_db(
        "SELECT channel_id FROM approved_channels",
        fetch=True
    )
    
    if not channels:
        await update.message.reply_text("ℹ️ No channels available for broadcasting.")
        return
    
    success = 0
    failed = 0
    
    broadcast_msg = f"""
📢 <b>Broadcast Message</b> 📢

{message}

<i>Sent by developer</i>
"""
    
    for channel in channels:
        try:
            await context.bot.send_message(
                chat_id=channel[0],
                text=broadcast_msg,
                parse_mode='HTML'
            )
            success += 1
        except Exception as e:
            logger.error(f"Failed to send to {channel[0]}: {e}")
            failed += 1
    
    await update.message.reply_text(
        f"✅ Broadcast completed!\n\nSuccess: {success}\nFailed: {failed}",
        parse_mode='HTML'
    )

@spam_protected
async def add_words(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Channel admin command to add words to filter."""
    if not update.effective_chat or not update.effective_user:
        return
    
    chat_id = str(update.effective_chat.id)
    user_id = update.effective_user.id
    
    is_approved = execute_db(
        "SELECT 1 FROM approved_channels WHERE channel_id = ?",
        (chat_id,),
        fetch=True
    )
    
    if not is_approved:
        await update.message.reply_text(f"❌ This channel is not approved. Contact the developer {DEVELOPER_USERNAME}")
        return
    
    if not await is_admin_or_owner(chat_id, user_id, context):
        await update.message.reply_text("❌ Only channel admins can use this command.")
        return
    
    if not context.args:
        await update.message.reply_text("ℹ️ Usage: /addwords word1 word2 word3")
        return
    
    added_count = 0
    for word in context.args:
        try:
            execute_db(
                "INSERT OR IGNORE INTO filtered_words VALUES (?, ?, ?, datetime('now'))",
                (chat_id, word.lower(), user_id)
            )
            added_count += 1
        except Exception as e:
            logger.error(f"Error adding word {word}: {e}")
    
    await update.message.reply_text(f"✅ Added {added_count} words to the filter list.")

@spam_protected
async def remove_word(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Remove a word from the filter list."""
    if not update.effective_chat or not update.effective_user:
        return
    
    chat_id = str(update.effective_chat.id)
    user_id = update.effective_user.id
    
    is_approved = execute_db(
        "SELECT 1 FROM approved_channels WHERE channel_id = ?",
        (chat_id,),
        fetch=True
    )
    
    if not is_approved:
        await update.message.reply_text(f"❌ This channel is not approved. Contact the developer {DEVELOPER_USERNAME}")
        return
    
    if not await is_admin_or_owner(chat_id, user_id, context):
        await update.message.reply_text("❌ Only channel admins can use this command.")
        return
    
    if not context.args:
        await update.message.reply_text("ℹ️ Usage: /removeword word")
        return
    
    word = context.args[0].lower()
    execute_db(
        "DELETE FROM filtered_words WHERE channel_id = ? AND word = ?",
        (chat_id, word)
    )
    await update.message.reply_text(f"✅ Removed '{word}' from the filter list.")

@spam_protected
async def list_words(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """List all filtered words for the current channel."""
    if not update.effective_chat or not update.effective_user:
        return
    
    chat_id = str(update.effective_chat.id)
    user_id = update.effective_user.id
    
    is_approved = execute_db(
        "SELECT 1 FROM approved_channels WHERE channel_id = ?",
        (chat_id,),
        fetch=True
    )
    
    if not is_approved:
        await update.message.reply_text(f"❌ This channel is not approved. Contact the developer {DEVELOPER_USERNAME}")
        return
    
    if not await is_admin_or_owner(chat_id, user_id, context):
        await update.message.reply_text("❌ Only channel admins can use this command.")
        return
    
    words = execute_db(
        "SELECT word FROM filtered_words WHERE channel_id = ?",
        (chat_id,),
        fetch=True
    )
    
    if not words:
        await update.message.reply_text("ℹ️ No words in the filter list yet.")
    else:
        words_list = "\n".join([word[0] for word in words])
        await update.message.reply_text(f"📋 Filtered words:\n{words_list}")

async def unmute_user_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the unmute button callback."""
    query = update.callback_query
    await query.answer()
    
    data = query.data.split(':')
    if len(data) != 3:
        return
    
    action, chat_id, user_id = data
    
    if action != 'unmute':
        return
    
    if not await is_admin_or_owner(chat_id, query.from_user.id, context):
        await query.answer("🔒 Only admins can unmute users!", show_alert=True)
        return
    
    try:
        await context.bot.restrict_chat_member(
            chat_id=chat_id,
            user_id=int(user_id),
            permissions=ChatPermissions(
                can_send_messages=True,
                can_send_media_messages=True,
                can_send_other_messages=True,
                can_add_web_page_previews=True
            )
        )
        
        execute_db(
            "DELETE FROM muted_users WHERE user_id = ? AND chat_id = ?",
            (int(user_id), chat_id)
        )
        
        original_text = query.message.text
        await query.message.edit_text(
            text=f"{original_text}\n\n✅ User has been unmuted by @{query.from_user.username}",
            reply_markup=None
        )
    except Exception as e:
        logger.error(f"Error unmuting user: {e}")
        await query.answer("❌ Failed to unmute user.", show_alert=True)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle all messages and filter links/bad words"""
    if not update.message or not update.effective_chat:
        return
    
    chat_id = str(update.effective_chat.id)
    user_id = update.effective_user.id
    user_name = update.effective_user.username or update.effective_user.full_name
    
    if update.effective_chat.type == "private":
        await update.message.reply_text("ℹ️ Please add me to a channel to use my features.")
        return
    
    is_approved = execute_db(
        "SELECT 1 FROM approved_channels WHERE channel_id = ?",
        (chat_id,),
        fetch=True
    )
    
    if not is_approved:
        return
    
    if await is_admin_or_owner(chat_id, user_id, context):
        return
    
    message_text = update.message.text or update.message.caption or ""
    
    # Check for links
    if "http://" in message_text.lower() or "https://" in message_text.lower():
        try:
            await update.message.delete()
        except Exception as e:
            logger.warning(f"Could not delete message: {e}")
            await context.bot.send_message(
                chat_id=chat_id,
                text=f"⚠️ Could not delete message from @{user_name}",
                reply_to_message_id=update.message.message_id
            )
            return
        
        await context.bot.send_message(
            chat_id=chat_id,
            text=f"🚫 @{user_name} - Links are not allowed here!",
            reply_to_message_id=update.message.message_id
        )
        return
    
    # Check for filtered words
    filtered_words = execute_db(
        "SELECT word FROM filtered_words WHERE channel_id = ?",
        (chat_id,),
        fetch=True
    )
    
    if filtered_words:
        message_lower = message_text.lower()
        for word_tuple in filtered_words:
            word = word_tuple[0]
            if word in message_lower:
                try:
                    await update.message.delete()
                except Exception as e:
                    logger.warning(f"Could not delete message: {e}")
                    await context.bot.send_message(
                        chat_id=chat_id,
                        text=f"⚠️ Could not delete message from @{user_name}",
                        reply_to_message_id=update.message.message_id
                    )
                    return
                
                mute_until = datetime.now() + timedelta(minutes=MUTE_DURATION_MINUTES)
                mute_reason = f"Used filtered word: '{word}'"
                
                try:
                    await context.bot.restrict_chat_member(
                        chat_id=chat_id,
                        user_id=user_id,
                        permissions=ChatPermissions(
                            can_send_messages=False,
                            can_send_media_messages=False,
                            can_send_other_messages=False,
                            can_add_web_page_previews=False
                        ),
                        until_date=mute_until
                    )
                except Exception as e:
                    logger.error(f"Error muting user: {e}")
                    return
                
                execute_db(
                    "INSERT OR REPLACE INTO muted_users VALUES (?, ?, ?, ?, ?, ?)",
                    (user_id, chat_id, mute_until.isoformat(), context.bot.id, 
                     update.message.message_id, mute_reason)
                )
                
                keyboard = [
                    [InlineKeyboardButton(
                        "🔊 Unmute User", 
                        callback_data=f"unmute:{chat_id}:{user_id}"
                    )]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                mute_msg = f"""
🚨 <b>User Muted</b> 🚨

👤 <b>User:</b> @{user_name}
⏳ <b>Duration:</b> {MUTE_DURATION_MINUTES} minutes
📝 <b>Reason:</b> {mute_reason}

<i>Admins can unmute using the button below</i>
"""
                mute_message = await context.bot.send_message(
                    chat_id=chat_id,
                    text=mute_msg,
                    reply_markup=reply_markup,
                    parse_mode='HTML'
                )
                
                execute_db(
                    "UPDATE muted_users SET mute_message_id = ? WHERE user_id = ? AND chat_id = ?",
                    (mute_message.message_id, user_id, chat_id)
                )
                return

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.error(msg="Exception while handling an update:", exc_info=context.error)

def main() -> None:
    init_db()
    
    application = ApplicationBuilder().token("7949936346:AAEJ8SA4vPH4Gveq2NBSDXY2vbC1jZ9WFdw").build()
    
    application.bot_data['start_time'] = time.time()
    
    command_handlers = [
        CommandHandler("start", start),
        CommandHandler("help", help_command),
        CommandHandler("alive", alive),
        CommandHandler("stats", stats),
        CommandHandler("addwords", add_words),
        CommandHandler("removeword", remove_word),
        CommandHandler("listwords", list_words),
        CommandHandler("add", add_channel),
        CommandHandler("channel", list_channels),
        CommandHandler("broadcast", broadcast)
    ]
    
    for handler in command_handlers:
        application.add_handler(handler)
    
    application.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, handle_message))
    application.add_handler(CallbackQueryHandler(unmute_user_callback, pattern="^unmute:"))
    application.add_error_handler(error_handler)
    
    logger.info("Bot is starting...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
