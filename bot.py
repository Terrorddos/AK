#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
🌟 Super Rose Bot 🌟
A feature-rich Telegram bot with economy system, moderation tools, and fun features.
ONLY FOR APPROVED CHANNELS - Contact @ABHISHEEK163 for access.
"""

import logging
import sqlite3
import random
import re
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ChatPermissions,
    User
)
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    CallbackQueryHandler,
    filters,
)
from telegram.error import BadRequest, TelegramError

# ======================
#  CONFIGURATION SETUP
# ======================
BOT_TOKEN = "7800244872:AAGOam8hjrQETyBhmMR67aKTWgDAcWliH-Q"  # Replace with your actual bot token
APPROVED_CHANNEL_ID = -1001867987504  # Replace with your approved channel ID
DEVELOPER_USERNAME = "ABHISHEEK163"  # Developer username for approvals
DB_NAME = "super_rose_bot.db"
DAILY_REWARD = 50
YT_REWARD = 100
KEY_PRICE_PER_DAY = 1000

# =================
#  LOGGING SETUP
# =================
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
    handlers=[
        logging.FileHandler("bot.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# =================
#  DATABASE CLASS
# =================
class Database:
    def __init__(self):
        self.conn = sqlite3.connect(DB_NAME)
        self.create_tables()

    def create_tables(self):
        cursor = self.conn.cursor()
        
        # Approved channels table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS approved_channels (
            channel_id INTEGER PRIMARY KEY,
            approved_by TEXT,
            approved_at TEXT
        )
        """)
        
        # Users table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER,
            channel_id INTEGER,
            username TEXT,
            first_name TEXT,
            last_name TEXT,
            t_money INTEGER DEFAULT 0,
            message_count INTEGER DEFAULT 0,
            last_daily TEXT,
            yt_claims_today INTEGER DEFAULT 0,
            last_claim_date TEXT,
            birthday TEXT,
            warnings INTEGER DEFAULT 0,
            PRIMARY KEY (user_id, channel_id)
        )
        """)
        
        # Keys table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS keys (
            key_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            channel_id INTEGER,
            key_type TEXT,
            days INTEGER,
            purchase_date TEXT,
            FOREIGN KEY(user_id, channel_id) REFERENCES users(user_id, channel_id)
        )
        """)
        
        # Warnings table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS warnings (
            warning_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            channel_id INTEGER,
            admin_id INTEGER,
            reason TEXT,
            timestamp TEXT,
            FOREIGN KEY(user_id, channel_id) REFERENCES users(user_id, channel_id)
        )
        """)
        
        # Special messages table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS special_messages (
            message_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            channel_id INTEGER,
            message_text TEXT,
            timestamp TEXT,
            FOREIGN KEY(user_id, channel_id) REFERENCES users(user_id, channel_id)
        )
        """)
        
        # Redeem codes table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS redeem_codes (
            code TEXT PRIMARY KEY,
            channel_id INTEGER,
            amount INTEGER,
            max_uses INTEGER,
            uses INTEGER DEFAULT 0,
            created_by INTEGER,
            created_at TEXT,
            FOREIGN KEY(channel_id) REFERENCES approved_channels(channel_id)
        )
        """)
        
        # Redeemed codes tracking
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS redeemed_codes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            channel_id INTEGER,
            code TEXT,
            redeemed_at TEXT,
            FOREIGN KEY(user_id, channel_id) REFERENCES users(user_id, channel_id),
            FOREIGN KEY(code) REFERENCES redeem_codes(code)
        )
        """)
        
        # YouTube videos table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS youtube_videos (
            video_id TEXT,
            channel_id INTEGER,
            added_by INTEGER,
            added_at TEXT,
            PRIMARY KEY (video_id, channel_id),
            FOREIGN KEY(channel_id) REFERENCES approved_channels(channel_id)
        )
        """)
        
        # Add the approved channel if not exists
        cursor.execute("""
        INSERT OR IGNORE INTO approved_channels (channel_id, approved_by, approved_at)
        VALUES (?, ?, ?)
        """, (APPROVED_CHANNEL_ID, "SYSTEM", datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        
        self.conn.commit()

    def is_channel_approved(self, channel_id: int) -> bool:
        cursor = self.conn.cursor()
        cursor.execute("SELECT 1 FROM approved_channels WHERE channel_id = ?", (channel_id,))
        return cursor.fetchone() is not None

    def approve_channel(self, channel_id: int, approved_by: str):
        cursor = self.conn.cursor()
        cursor.execute("""
        INSERT INTO approved_channels (channel_id, approved_by, approved_at)
        VALUES (?, ?, ?)
        """, (channel_id, approved_by, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        self.conn.commit()

    def update_user(self, user_id: int, channel_id: int, username: str, first_name: str, last_name: str):
        cursor = self.conn.cursor()
        cursor.execute("""
        INSERT OR IGNORE INTO users (user_id, channel_id, username, first_name, last_name) 
        VALUES (?, ?, ?, ?, ?)
        """, (user_id, channel_id, username, first_name, last_name))
        
        cursor.execute("""
        UPDATE users 
        SET username = ?, first_name = ?, last_name = ?
        WHERE user_id = ? AND channel_id = ?
        """, (username, first_name, last_name, user_id, channel_id))
        self.conn.commit()

    def get_user(self, user_id: int, channel_id: int) -> Optional[Dict]:
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM users WHERE user_id = ? AND channel_id = ?", (user_id, channel_id))
        result = cursor.fetchone()
        
        if result:
            columns = [column[0] for column in cursor.description]
            return dict(zip(columns, result))
        return None

    def add_t_money(self, user_id: int, channel_id: int, amount: int):
        cursor = self.conn.cursor()
        cursor.execute("""
        UPDATE users 
        SET t_money = t_money + ?
        WHERE user_id = ? AND channel_id = ?
        """, (amount, user_id, channel_id))
        self.conn.commit()

    def remove_t_money(self, user_id: int, channel_id: int, amount: int) -> bool:
        cursor = self.conn.cursor()
        cursor.execute("SELECT t_money FROM users WHERE user_id = ? AND channel_id = ?", (user_id, channel_id))
        result = cursor.fetchone()
        if not result:
            return False
            
        balance = result[0]
        if balance >= amount:
            cursor.execute("""
            UPDATE users 
            SET t_money = t_money - ?
            WHERE user_id = ? AND channel_id = ?
            """, (amount, user_id, channel_id))
            self.conn.commit()
            return True
        return False

    def get_balance(self, user_id: int, channel_id: int) -> int:
        cursor = self.conn.cursor()
        cursor.execute("SELECT t_money FROM users WHERE user_id = ? AND channel_id = ?", (user_id, channel_id))
        result = cursor.fetchone()
        return result[0] if result else 0

    def increment_message_count(self, user_id: int, channel_id: int):
        cursor = self.conn.cursor()
        cursor.execute("""
        UPDATE users 
        SET message_count = message_count + 1
        WHERE user_id = ? AND channel_id = ?
        """, (user_id, channel_id))
        self.conn.commit()

    def get_message_count(self, user_id: int, channel_id: int) -> int:
        cursor = self.conn.cursor()
        cursor.execute("SELECT message_count FROM users WHERE user_id = ? AND channel_id = ?", (user_id, channel_id))
        result = cursor.fetchone()
        return result[0] if result else 0

    def set_last_daily(self, user_id: int, channel_id: int, date: str):
        cursor = self.conn.cursor()
        cursor.execute("""
        UPDATE users 
        SET last_daily = ?
        WHERE user_id = ? AND channel_id = ?
        """, (date, user_id, channel_id))
        self.conn.commit()

    def get_last_daily(self, user_id: int, channel_id: int) -> Optional[str]:
        cursor = self.conn.cursor()
        cursor.execute("SELECT last_daily FROM users WHERE user_id = ? AND channel_id = ?", (user_id, channel_id))
        result = cursor.fetchone()
        return result[0] if result else None

    def get_top_users(self, channel_id: int, limit: int = 10) -> List[Tuple[int, str, int, int]]:
        cursor = self.conn.cursor()
        cursor.execute("""
        SELECT user_id, first_name, t_money, message_count 
        FROM users 
        WHERE channel_id = ?
        ORDER BY t_money DESC 
        LIMIT ?
        """, (channel_id, limit))
        return cursor.fetchall()

    def increment_yt_claim(self, user_id: int, channel_id: int):
        # Reset claims if it's a new day
        cursor = self.conn.cursor()
        cursor.execute("SELECT last_claim_date FROM users WHERE user_id = ? AND channel_id = ?", (user_id, channel_id))
        result = cursor.fetchone()
        
        today = datetime.now().strftime("%Y-%m-%d")
        if not result or result[0] != today:
            cursor.execute("""
            UPDATE users 
            SET yt_claims_today = 1,
                last_claim_date = ?
            WHERE user_id = ? AND channel_id = ?
            """, (today, user_id, channel_id))
        else:
            cursor.execute("""
            UPDATE users 
            SET yt_claims_today = yt_claims_today + 1
            WHERE user_id = ? AND channel_id = ?
            """, (user_id, channel_id))
        self.conn.commit()

    def get_yt_claims_today(self, user_id: int, channel_id: int) -> int:
        cursor = self.conn.cursor()
        cursor.execute("SELECT yt_claims_today, last_claim_date FROM users WHERE user_id = ? AND channel_id = ?", (user_id, channel_id))
        result = cursor.fetchone()
        
        if not result:
            return 0
            
        claims, last_date = result
        today = datetime.now().strftime("%Y-%m-%d")
        
        if last_date != today:
            return 0
        return claims

    def add_key(self, user_id: int, channel_id: int, key_type: str, days: int):
        cursor = self.conn.cursor()
        cursor.execute("""
        INSERT INTO keys (user_id, channel_id, key_type, days, purchase_date)
        VALUES (?, ?, ?, ?, ?)
        """, (user_id, channel_id, key_type, days, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        self.conn.commit()

    def get_user_keys(self, user_id: int, channel_id: int) -> List[Dict]:
        cursor = self.conn.cursor()
        cursor.execute("""
        SELECT key_id, key_type, days, purchase_date 
        FROM keys 
        WHERE user_id = ? AND channel_id = ?
        """, (user_id, channel_id))
        
        results = cursor.fetchall()
        if not results:
            return []
            
        columns = [column[0] for column in cursor.description]
        return [dict(zip(columns, row)) for row in results]

    def set_birthday(self, user_id: int, channel_id: int, date: str):
        cursor = self.conn.cursor()
        cursor.execute("""
        UPDATE users 
        SET birthday = ?
        WHERE user_id = ? AND channel_id = ?
        """, (date, user_id, channel_id))
        self.conn.commit()

    def get_birthday(self, user_id: int, channel_id: int) -> Optional[str]:
        cursor = self.conn.cursor()
        cursor.execute("SELECT birthday FROM users WHERE user_id = ? AND channel_id = ?", (user_id, channel_id))
        result = cursor.fetchone()
        return result[0] if result else None

    def set_special_message(self, message_text: str, user_id: int, channel_id: int):
        cursor = self.conn.cursor()
        # Only keep one special message at a time per channel
        cursor.execute("DELETE FROM special_messages WHERE channel_id = ?", (channel_id,))
        cursor.execute("""
        INSERT INTO special_messages (user_id, channel_id, message_text, timestamp)
        VALUES (?, ?, ?, ?)
        """, (user_id, channel_id, message_text, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        self.conn.commit()

    def get_special_message(self, channel_id: int) -> Optional[Dict]:
        cursor = self.conn.cursor()
        cursor.execute("""
        SELECT message_id, user_id, message_text, timestamp 
        FROM special_messages 
        WHERE channel_id = ?
        ORDER BY message_id DESC 
        LIMIT 1
        """, (channel_id,))
        result = cursor.fetchone()
        
        if result:
            columns = [column[0] for column in cursor.description]
            return dict(zip(columns, result))
        return None

    def delete_special_message(self, message_id: int):
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM special_messages WHERE message_id = ?", (message_id,))
        self.conn.commit()

    def add_warning(self, user_id: int, channel_id: int, admin_id: int, reason: str):
        cursor = self.conn.cursor()
        cursor.execute("""
        INSERT INTO warnings (user_id, channel_id, admin_id, reason, timestamp)
        VALUES (?, ?, ?, ?, ?)
        """, (user_id, channel_id, admin_id, reason, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        
        cursor.execute("""
        UPDATE users 
        SET warnings = warnings + 1
        WHERE user_id = ? AND channel_id = ?
        """, (user_id, channel_id))
        self.conn.commit()

    def get_warnings(self, user_id: int, channel_id: int) -> List[Dict]:
        cursor = self.conn.cursor()
        cursor.execute("""
        SELECT warning_id, admin_id, reason, timestamp 
        FROM warnings 
        WHERE user_id = ? AND channel_id = ?
        ORDER BY timestamp DESC
        """, (user_id, channel_id))
        
        results = cursor.fetchall()
        if not results:
            return []
            
        columns = [column[0] for column in cursor.description]
        return [dict(zip(columns, row)) for row in results]

    def clear_warnings(self, user_id: int, channel_id: int):
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM warnings WHERE user_id = ? AND channel_id = ?", (user_id, channel_id))
        cursor.execute("""
        UPDATE users 
        SET warnings = 0
        WHERE user_id = ? AND channel_id = ?
        """, (user_id, channel_id))
        self.conn.commit()

    # Redeem code methods
    def create_redeem_code(self, code: str, channel_id: int, amount: int, max_uses: int, created_by: int):
        cursor = self.conn.cursor()
        cursor.execute("""
        INSERT INTO redeem_codes (code, channel_id, amount, max_uses, created_by, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """, (code, channel_id, amount, max_uses, created_by, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        self.conn.commit()
    
    def get_redeem_code(self, code: str, channel_id: int) -> Optional[Dict]:
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM redeem_codes WHERE code = ? AND channel_id = ?", (code, channel_id))
        result = cursor.fetchone()
        if result:
            columns = [column[0] for column in cursor.description]
            return dict(zip(columns, result))
        return None
    
    def redeem_code(self, user_id: int, channel_id: int, code: str) -> bool:
        cursor = self.conn.cursor()
        cursor.execute("SELECT amount, max_uses, uses FROM redeem_codes WHERE code = ? AND channel_id = ?", (code, channel_id))
        result = cursor.fetchone()
        
        if not result:
            return False
            
        amount, max_uses, uses = result
        if uses >= max_uses:
            return False
            
        # Check if user already redeemed this code
        cursor.execute("SELECT id FROM redeemed_codes WHERE user_id = ? AND channel_id = ? AND code = ?", (user_id, channel_id, code))
        if cursor.fetchone():
            return False
            
        # Update code uses
        cursor.execute("""
        UPDATE redeem_codes 
        SET uses = uses + 1 
        WHERE code = ? AND channel_id = ?
        """, (code, channel_id))
        
        # Add to redeemed tracking
        cursor.execute("""
        INSERT INTO redeemed_codes (user_id, channel_id, code, redeemed_at)
        VALUES (?, ?, ?, ?)
        """, (user_id, channel_id, code, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        
        # Add money to user
        cursor.execute("""
        UPDATE users 
        SET t_money = t_money + ?
        WHERE user_id = ? AND channel_id = ?
        """, (amount, user_id, channel_id))
        
        self.conn.commit()
        return True
    
    # YouTube video methods
    def add_youtube_video(self, video_id: str, channel_id: int, added_by: int):
        cursor = self.conn.cursor()
        try:
            cursor.execute("""
            INSERT INTO youtube_videos (video_id, channel_id, added_by, added_at)
            VALUES (?, ?, ?, ?)
            """, (video_id, channel_id, added_by, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
            self.conn.commit()
            return True
        except sqlite3.IntegrityError:  # Video already exists
            return False
    
    def get_youtube_videos(self, channel_id: int) -> List[Dict]:
        cursor = self.conn.cursor()
        cursor.execute("""
        SELECT video_id, added_by, added_at 
        FROM youtube_videos 
        WHERE channel_id = ?
        ORDER BY added_at DESC
        """, (channel_id,))
        results = cursor.fetchall()
        if not results:
            return []
            
        columns = [column[0] for column in cursor.description]
        return [dict(zip(columns, row)) for row in results]
    
    def remove_youtube_video(self, video_id: str, channel_id: int) -> bool:
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM youtube_videos WHERE video_id = ? AND channel_id = ?", (video_id, channel_id))
        self.conn.commit()
        return cursor.rowcount > 0

# Initialize database
db = Database()

# =====================
#  HELPER FUNCTIONS
# =====================
def generate_code(length=8):
    chars = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    return ''.join(random.choice(chars) for _ in range(length))

async def is_approved_channel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Check if the command is being used in an approved channel"""
    if update.effective_chat.type == "private":
        await update.message.reply_text("❌ This bot only works in approved channels!")
        return False
    
    channel_id = update.effective_chat.id
    if not db.is_channel_approved(channel_id):
        await update.message.reply_text(
            f"❌ This channel is not approved to use this bot!\n"
            f"Contact @{DEVELOPER_USERNAME} for approval.",
            parse_mode="Markdown"
        )
        return False
    return True

async def is_admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Check if user is admin"""
    if update.effective_chat.type == "private":
        return False
        
    try:
        user = await context.bot.get_chat_member(
            chat_id=update.effective_chat.id,
            user_id=update.effective_user.id
        )
        return user.status in ["administrator", "creator"]
    except TelegramError as e:
        logger.error(f"Error checking admin status: {e}")
        return False

async def enforce_admin_commands(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Check if bot has admin permissions for admin commands"""
    if update.effective_chat.type == "private":
        await update.message.reply_text("❌ This command only works in groups!")
        return False
        
    try:
        bot_member = await context.bot.get_chat_member(
            chat_id=update.effective_chat.id,
            user_id=context.bot.id
        )
        
        if bot_member.status != "administrator":
            await update.message.reply_text("❌ I need to be an admin to perform this action!")
            return False
            
        return True
    except TelegramError as e:
        logger.error(f"Error checking bot admin status: {e}")
        await update.message.reply_text("❌ Error checking permissions!")
        return False

async def send_warning(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int, reason: str):
    """Send warning message to user"""
    try:
        await context.bot.send_message(
            chat_id=user_id,
            text=f"⚠️ You received a warning in {update.effective_chat.title}\n"
                 f"📝 Reason: {reason}\n\n"
                 "Please follow the group rules to avoid further actions."
        )
    except Exception as e:
        logger.error(f"Failed to send warning to user {user_id}: {e}")

async def parse_time(time_str: str) -> Optional[timedelta]:
    """Parse time string like 1h, 30m, 2d into timedelta"""
    try:
        if time_str.endswith('m'):
            minutes = int(time_str[:-1])
            return timedelta(minutes=minutes)
        elif time_str.endswith('h'):
            hours = int(time_str[:-1])
            return timedelta(hours=hours)
        elif time_str.endswith('d'):
            days = int(time_str[:-1])
            return timedelta(days=days)
        else:
            # Default to hours if no unit specified
            hours = int(time_str)
            return timedelta(hours=hours)
    except ValueError:
        return None

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Log errors caused by updates."""
    logger.error(msg="Exception while handling an update:", exc_info=context.error)
    if update and hasattr(update, 'message'):
        try:
            await update.message.reply_text("❌ An error occurred while processing your request!")
        except:
            pass

async def get_target_user(update: Update, context: ContextTypes.DEFAULT_TYPE) -> Optional[dict]:
    """Helper function to get target user from message"""
    try:
        # Check if replying to a message
        if update.message.reply_to_message:
            target = update.message.reply_to_message.from_user
            return {
                'id': target.id,
                'username': target.username,
                'first_name': target.first_name
            }
        
        # Check for username mention
        if context.args and context.args[0].startswith('@'):
            username = context.args[0][1:]
            cursor = db.conn.cursor()
            cursor.execute("SELECT user_id, username, first_name FROM users WHERE username = ? AND channel_id = ?", 
                         (username, update.effective_chat.id))
            result = cursor.fetchone()
            if result:
                return {
                    'id': result[0],
                    'username': result[1],
                    'first_name': result[2]
                }
        
        # Check for user ID
        if context.args and context.args[0].isdigit():
            user_id = int(context.args[0])
            user_data = db.get_user(user_id, update.effective_chat.id)
            if user_data:
                return {
                    'id': user_id,
                    'username': user_data.get('username'),
                    'first_name': user_data.get('first_name')
                }
        
        return None
    except Exception as e:
        logger.error(f"Error getting target user: {e}")
        return None

# ===================
#  COMMAND HANDLERS
# ===================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send a message when the command /start is issued."""
    try:
        if not await is_approved_channel(update, context):
            return
            
        user = update.effective_user
        db.update_user(user.id, update.effective_chat.id, user.username, user.first_name, user.last_name)
        
        await update.message.reply_text(
            f"🌟 Welcome to Super Rose Bot, {user.first_name}! 🌟\n\n"
            "I'm a feature-rich bot with economy system, moderation tools, and fun features.\n"
            "Use /help to see what I can do!",
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.error(f"Error in start command: {e}")
        await update.message.reply_text("❌ An error occurred!")

async def help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send a help message when the command /help is issued."""
    try:
        if not await is_approved_channel(update, context):
            return
            
        help_text = f"""
🌟 *Super Rose Bot Help* 🌟
*Approved for this channel only - Contact @{DEVELOPER_USERNAME} for access*

*💰 Economy Commands*:
/daily - Claim your daily reward
/balance - Check your T-Money balance
/top - See the richest users in this channel
/claim_yt - Claim YouTube watching reward
/buykey - Buy premium keys
/mykeys - View your purchased keys
/redeem <code> - Redeem a code for T-Money
/gift @user <amount> - Gift T-Money to another user

*🎉 Fun Commands*:
/setbirthday <DD-MM> - Set your birthday
/birthday - Show your birthday
/specialmsg - Show channel's special message

*🛠 Admin Commands*:
/warn <user> <reason> - Warn a user
/mute <user> <time> - Mute a user (e.g., 1h, 30m, 2d)
/unmute <user> - Unmute a user
/kick <user> <reason> - Kick a user
/ban <user> <reason> - Ban a user
/addmoney <user> <amount> - Add T-Money to user
/removemoney <user> <amount> - Remove T-Money from user
/addkey <user> <days> - Add premium key to user
/clearwarns <user> - Clear user's warnings
/set_specialmsg <message> - Set special channel message
/del_specialmsg - Delete special channel message
/gen <amount> <uses> - Generate redeem code
/add_yt <url> - Add YouTube video for claims
/list_yt - List available YouTube videos
/remove_yt <index> - Remove YouTube video
/announcement <message> - Make an announcement

*ℹ️ Info Commands*:
/info - Show your info
/id - Get your user ID
/rank - Show your message rank
/admins - List channel admins
        """
        
        await update.message.reply_text(help_text, parse_mode="Markdown")
    except BadRequest:
        # If Markdown fails, send as plain text
        await update.message.reply_text(help_text)
    except Exception as e:
        logger.error(f"Error in help command: {e}")
        await update.message.reply_text("❌ An error occurred!")

async def approve_channel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Approve a new channel to use the bot (developer only)"""
    try:
        user = update.effective_user
        if not user.username or user.username.lower() != DEVELOPER_USERNAME.lower():
            await update.message.reply_text("❌ Only the developer can approve channels!")
            return
            
        if not context.args or not context.args[0].isdigit():
            await update.message.reply_text("Usage: /approve_channel <channel_id>")
            return
            
        channel_id = int(context.args[0])
        if db.is_channel_approved(channel_id):
            await update.message.reply_text("✅ This channel is already approved!")
            return
            
        db.approve_channel(channel_id, user.username)
        await update.message.reply_text(
            f"✅ Channel {channel_id} has been approved!\n"
            "The bot can now be added to this channel.",
            parse_mode="Markdown"
        )
        
        # Try to send a message to the channel
        try:
            await context.bot.send_message(
                chat_id=channel_id,
                text=f"🎉 This channel has been approved by @{user.username} to use Super Rose Bot!\n"
                     "You can now use all bot features in this channel.",
                parse_mode="Markdown"
            )
        except Exception as e:
            logger.error(f"Could not send message to channel {channel_id}: {e}")
            
    except Exception as e:
        logger.error(f"Error in approve_channel command: {e}")
        await update.message.reply_text("❌ An error occurred while approving channel!")

async def info_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show user information."""
    try:
        if not await is_approved_channel(update, context):
            return
            
        user = update.effective_user
        target_user = user
        
        # Check if replying to a message or has username argument
        if update.message.reply_to_message:
            target_user = update.message.reply_to_message.from_user
        elif context.args and len(context.args) > 0:
            if context.args[0].startswith('@'):
                username = context.args[0][1:]
                cursor = db.conn.cursor()
                cursor.execute("SELECT user_id, username, first_name FROM users WHERE username = ? AND channel_id = ?", 
                             (username, update.effective_chat.id))
                result = cursor.fetchone()
                if result:
                    target_user_id = result[0]
                    target_user = type('', (), {'id': target_user_id, 'username': result[1], 'first_name': result[2]})()
            elif context.args[0].isdigit():
                target_user_id = int(context.args[0])
                user_data = db.get_user(target_user_id, update.effective_chat.id)
                if user_data:
                    target_user = type('', (), {'id': target_user_id, 'username': user_data.get('username'), 'first_name': user_data.get('first_name')})()

        db.update_user(target_user.id, update.effective_chat.id, target_user.username, target_user.first_name, getattr(target_user, 'last_name', None))
        user_data = db.get_user(target_user.id, update.effective_chat.id)
        
        if not user_data:
            await update.message.reply_text("❌ User not found in this channel!")
            return
        
        birthday = user_data.get('birthday', 'Not set')
        warnings = user_data.get('warnings', 0)
        keys = db.get_user_keys(target_user.id, update.effective_chat.id)
        premium_days = sum(key['days'] for key in keys) if keys else 0
        
        response = (
            f"👤 *User Info*\n"
            f"🆔 ID: `{target_user.id}`\n"
            f"👤 Name: {target_user.first_name}\n"
            f"📛 Username: @{target_user.username if target_user.username else 'N/A'}\n"
            f"💰 Balance: {user_data['t_money']}T\n"
            f"📨 Messages: {user_data['message_count']}\n"
            f"🎂 Birthday: {birthday}\n"
            f"⚠️ Warnings: {warnings}\n"
            f"🌟 Premium: {'Yes' if premium_days > 0 else 'No'}"
        )
        
        await update.message.reply_text(response, parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Error in info command: {e}")
        await update.message.reply_text("❌ An error occurred while fetching user info!")

async def id_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Get user ID."""
    try:
        if not await is_approved_channel(update, context):
            return
            
        user = update.effective_user
        await update.message.reply_text(f"🆔 Your ID: `{user.id}`", parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Error in id command: {e}")
        await update.message.reply_text("❌ An error occurred!")

async def rank(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show user's message rank."""
    try:
        if not await is_approved_channel(update, context):
            return
            
        user = update.effective_user
        db.update_user(user.id, update.effective_chat.id, user.username, user.first_name, user.last_name)
        
        message_count = db.get_message_count(user.id, update.effective_chat.id)
        await update.message.reply_text(
            f"📊 *Your Stats*\n"
            f"👤 Name: {user.first_name}\n"
            f"📨 Messages: {message_count}",
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.error(f"Error in rank command: {e}")
        await update.message.reply_text("❌ An error occurred!")

async def top(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show top users by T-Money."""
    try:
        if not await is_approved_channel(update, context):
            return
            
        top_users = db.get_top_users(update.effective_chat.id, 10)
        
        if not top_users:
            await update.message.reply_text("❌ No users found in this channel!")
            return
        
        response = "🏆 *Top Users by T-Money* 🏆\n\n"
        for i, (user_id, first_name, t_money, msg_count) in enumerate(top_users, 1):
            response += f"{i}. {first_name} - {t_money}T (📨 {msg_count})\n"
        
        await update.message.reply_text(response, parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Error in top command: {e}")
        await update.message.reply_text("❌ An error occurred while fetching top users!")

async def daily(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Claim daily reward."""
    try:
        if not await is_approved_channel(update, context):
            return
            
        user = update.effective_user
        db.update_user(user.id, update.effective_chat.id, user.username, user.first_name, user.last_name)
        
        last_daily = db.get_last_daily(user.id, update.effective_chat.id)
        today = datetime.now().strftime("%Y-%m-%d")
        
        if last_daily == today:
            await update.message.reply_text(
                "⏳ You've already claimed your daily reward today!\n"
                "Come back tomorrow for more T-Money!",
                parse_mode="Markdown"
            )
            return
        
        db.add_t_money(user.id, update.effective_chat.id, DAILY_REWARD)
        db.set_last_daily(user.id, update.effective_chat.id, today)
        
        await update.message.reply_text(
            f"🎉 You claimed your daily reward of {DAILY_REWARD}T!\n"
            f"💰 New balance: {db.get_balance(user.id, update.effective_chat.id)}T",
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.error(f"Error in daily command: {e}")
        await update.message.reply_text("❌ An error occurred while claiming daily reward!")

async def claim_yt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Claim YouTube watching reward"""
    try:
        if not await is_approved_channel(update, context):
            return
            
        user = update.effective_user
        db.update_user(user.id, update.effective_chat.id, user.username, user.first_name, user.last_name)
        
        claims_today = db.get_yt_claims_today(user.id, update.effective_chat.id)
        max_claims = 5
        
        if claims_today >= max_claims:
            await update.message.reply_text(
                f"⚠️ You've already claimed the YouTube reward {max_claims} times today.\n"
                "Come back tomorrow for more!",
                parse_mode="Markdown"
            )
            return
        
        # Get available videos
        videos = db.get_youtube_videos(update.effective_chat.id)
        if not videos:
            await update.message.reply_text("❌ No YouTube videos available for claims in this channel!")
            return
            
        # Select a random YouTube video
        video = random.choice(videos)
        yt_url = f"https://www.youtube.com/watch?v={video['video_id']}"
        
        keyboard = [
            [
                InlineKeyboardButton("📺 Watch Video", url=yt_url),
                InlineKeyboardButton("✅ Confirm Watch", callback_data=f"yt_confirm_{user.id}_{update.effective_chat.id}")
            ]
        ]
        
        await update.message.reply_text(
            "📺 *YouTube Reward* 📺\n\n"
            "1. Click 'Watch Video' and watch for at least 30 seconds\n"
            "2. Return and click 'Confirm Watch' to claim\n\n"
            f"🎁 Reward: {YT_REWARD}T\n"
            f"📊 Claims today: {claims_today}/{max_claims}",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard),
            disable_web_page_preview=True
        )
    except Exception as e:
        logger.error(f"Error in claim_yt command: {e}")
        await update.message.reply_text("❌ An error occurred while setting up YouTube reward!")

async def yt_confirmation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle YouTube confirmation callback"""
    try:
        query = update.callback_query
        await query.answer()
        
        parts = query.data.split('_')
        user_id = int(parts[2])
        channel_id = int(parts[3])
        
        if query.from_user.id != user_id:
            await query.edit_message_text("❌ This confirmation is not for you!")
            return
        
        if not db.is_channel_approved(channel_id):
            await query.edit_message_text("❌ This channel is no longer approved!")
            return
        
        db.increment_yt_claim(user_id, channel_id)
        db.add_t_money(user_id, channel_id, YT_REWARD)
        
        await query.edit_message_text(
            f"🎉 You received {YT_REWARD}T for watching YouTube!\n"
            f"💰 New balance: {db.get_balance(user_id, channel_id)}T",
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.error(f"Error in yt_confirmation: {e}")
        try:
            await query.edit_message_text("❌ An error occurred while processing your reward!")
        except:
            pass

async def buy_key(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Buy premium key"""
    try:
        if not await is_approved_channel(update, context):
            return
            
        user = update.effective_user
        db.update_user(user.id, update.effective_chat.id, user.username, user.first_name, user.last_name)
        
        if not context.args or not context.args[0].isdigit():
            await update.message.reply_text("Usage: /buykey <days>")
            return
        
        days = int(context.args[0])
        total_cost = days * KEY_PRICE_PER_DAY
        balance = db.get_balance(user.id, update.effective_chat.id)
        
        if balance < total_cost:
            await update.message.reply_text(
                f"❌ You don't have enough T-Money!\n"
                f"💰 Needed: {total_cost}T\n"
                f"💵 Your balance: {balance}T",
                parse_mode="Markdown"
            )
            return
        
        if db.remove_t_money(user.id, update.effective_chat.id, total_cost):
            db.add_key(user.id, update.effective_chat.id, "premium", days)
            await update.message.reply_text(
                f"🔑 Premium key purchased!\n"
                f"⏳ Duration: {days} days\n"
                f"💵 Cost: {total_cost}T\n"
                f"💰 New balance: {db.get_balance(user.id, update.effective_chat.id)}T",
                parse_mode="Markdown"
            )
        else:
            await update.message.reply_text("❌ Transaction failed!")
    except Exception as e:
        logger.error(f"Error in buy_key command: {e}")
        await update.message.reply_text("❌ An error occurred while purchasing key!")

async def my_keys(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show user's purchased keys"""
    try:
        if not await is_approved_channel(update, context):
            return
            
        user = update.effective_user
        keys = db.get_user_keys(user.id, update.effective_chat.id)
        
        if not keys:
            await update.message.reply_text("❌ You don't have any keys in this channel!")
            return
        
        response = "🔑 *Your Premium Keys* 🔑\n\n"
        for key in keys:
            purchase_date = datetime.strptime(key['purchase_date'], "%Y-%m-%d %H:%M:%S")
            expiry_date = purchase_date + timedelta(days=key['days'])
            response += (
                f"🔹 Type: {key['key_type']}\n"
                f"⏳ Days: {key['days']}\n"
                f"🛒 Purchased: {purchase_date.strftime('%Y-%m-%d')}\n"
                f"📅 Expires: {expiry_date.strftime('%Y-%m-%d')}\n\n"
            )
        
        await update.message.reply_text(response, parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Error in my_keys command: {e}")
        await update.message.reply_text("❌ An error occurred while fetching your keys!")

async def set_birthday(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Set user's birthday"""
    try:
        if not await is_approved_channel(update, context):
            return
            
        user = update.effective_user
        
        if not context.args or len(context.args) != 1:
            await update.message.reply_text("Usage: /setbirthday DD-MM (e.g., /setbirthday 15-04)")
            return
        
        date_str = context.args[0]
        try:
            # Validate date format
            day, month = map(int, date_str.split('-'))
            if not (1 <= month <= 12 and 1 <= day <= 31):
                raise ValueError
            
            # Store as MM-DD format for easier sorting
            db.set_birthday(user.id, update.effective_chat.id, f"{month:02d}-{day:02d}")
            await update.message.reply_text(
                f"🎂 Birthday set to {day:02d}-{month:02d}!\n"
                "You'll receive a special message on your birthday!",
                parse_mode="Markdown"
            )
        except (ValueError, IndexError):
            await update.message.reply_text("❌ Invalid date format. Use DD-MM (e.g., 15-04)")
    except Exception as e:
        logger.error(f"Error in set_birthday command: {e}")
        await update.message.reply_text("❌ An error occurred while setting birthday!")

async def show_birthday(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show user's birthday"""
    try:
        if not await is_approved_channel(update, context):
            return
            
        user = update.effective_user
        target_user = user
        
        # Check if replying to a message or has username argument
        if update.message.reply_to_message:
            target_user = update.message.reply_to_message.from_user
        elif context.args and len(context.args) > 0:
            if context.args[0].startswith('@'):
                username = context.args[0][1:]
                cursor = db.conn.cursor()
                cursor.execute("SELECT user_id, username, first_name FROM users WHERE username = ? AND channel_id = ?", 
                             (username, update.effective_chat.id))
                result = cursor.fetchone()
                if result:
                    target_user_id = result[0]
                    target_user = type('', (), {'id': target_user_id, 'username': result[1], 'first_name': result[2]})()
            elif context.args[0].isdigit():
                target_user_id = int(context.args[0])
                user_data = db.get_user(target_user_id, update.effective_chat.id)
                if user_data:
                    target_user = type('', (), {'id': target_user_id, 'username': user_data.get('username'), 'first_name': user_data.get('first_name')})()
        
        birthday = db.get_birthday(target_user.id, update.effective_chat.id)
        if not birthday:
            await update.message.reply_text(
                f"❌ {target_user.first_name} hasn't set their birthday yet!",
                parse_mode="Markdown"
            )
            return
        
        # Convert from stored MM-DD to DD-MM for display
        month, day = birthday.split('-')
        await update.message.reply_text(
            f"🎂 {target_user.first_name}'s birthday is on {day}-{month}!",
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.error(f"Error in show_birthday command: {e}")
        await update.message.reply_text("❌ An error occurred while fetching birthday!")

async def special_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show special channel message"""
    try:
        if not await is_approved_channel(update, context):
            return
            
        special_msg = db.get_special_message(update.effective_chat.id)
        if not special_msg:
            await update.message.reply_text("❌ No special message set for this channel!")
            return
        
        user_data = db.get_user(special_msg['user_id'], update.effective_chat.id)
        await update.message.reply_text(
            f"🌟 *Special Channel Message* 🌟\n\n"
            f"{special_msg['message_text']}\n\n"
            f"📅 Set by: {user_data['first_name']} on {special_msg['timestamp']}",
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.error(f"Error in special_message command: {e}")
        await update.message.reply_text("❌ An error occurred while fetching special message!")

async def set_special_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Set special channel message (admin only)"""
    try:
        if not await is_approved_channel(update, context):
            return
            
        if not await is_admin(update, context):
            await update.message.reply_text("❌ This command is for admins only!")
            return
        
        if not context.args:
            await update.message.reply_text("Usage: /set_specialmsg <message>")
            return
        
        message_text = ' '.join(context.args)
        db.set_special_message(message_text, update.effective_user.id, update.effective_chat.id)
        await update.message.reply_text("✅ Special channel message set!")
    except Exception as e:
        logger.error(f"Error in set_special_message command: {e}")
        await update.message.reply_text("❌ An error occurred while setting special message!")

async def del_special_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Delete special channel message (admin only)"""
    try:
        if not await is_approved_channel(update, context):
            return
            
        if not await is_admin(update, context):
            await update.message.reply_text("❌ This command is for admins only!")
            return
        
        special_msg = db.get_special_message(update.effective_chat.id)
        if not special_msg:
            await update.message.reply_text("❌ No special message to delete.")
            return
        
        db.delete_special_message(special_msg.get('id', 0))
        await update.message.reply_text("✅ Special message deleted!")
    except Exception as e:
        logger.error(f"Error in del_special_message command: {e}")
        await update.message.reply_text("❌ An error occurred while deleting special message!")

async def announcement(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Make an announcement (admin only)"""
    try:
        if not await is_approved_channel(update, context):
            return
            
        if not await is_admin(update, context):
            await update.message.reply_text("❌ This command is for admins only!")
            return
        
        if not context.args:
            await update.message.reply_text("Usage: /announcement <message>")
            return
        
        message_text = ' '.join(context.args)
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=f"📢 *Announcement* 📢\n\n{message_text}",
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.error(f"Error in announcement command: {e}")
        await update.message.reply_text("❌ An error occurred while making announcement!")

async def admins_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """List channel admins"""
    try:
        if not await is_approved_channel(update, context):
            return
            
        if update.effective_chat.type == "private":
            await update.message.reply_text("❌ This command only works in channels/groups!")
            return
        
        admins = await context.bot.get_chat_administrators(update.effective_chat.id)
        admin_list = []
        
        for admin in admins:
            if admin.user.is_bot:
                continue
            name = admin.user.first_name
            if admin.user.username:
                name += f" (@{admin.user.username})"
            if admin.status == "creator":
                name = "👑 " + name
            admin_list.append(name)
        
        await update.message.reply_text(
            "🛡 *Channel Admins* 🛡\n\n" + "\n".join(admin_list),
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.error(f"Error in admins_command: {e}")
        await update.message.reply_text("❌ An error occurred while fetching admins!")

# =====================
#  MODERATION COMMANDS
# =====================
async def warn_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Warn a user (admin only)"""
    try:
        if not await is_approved_channel(update, context):
            return
            
        if not await is_admin(update, context):
            await update.message.reply_text("❌ This command is for admins only!")
            return
        
        target_user = await get_target_user(update, context)
        if not target_user:
            await update.message.reply_text(
                "❌ Please either:\n"
                "1. Reply to user's message\n"
                "2. Mention with @username\n"
                "3. Provide user ID"
            )
            return
        
        reason = ' '.join(context.args[1:]) if len(context.args) > 1 else "No reason provided"
        await send_warning(update, context, target_user['id'], reason)
        
        db.add_warning(target_user['id'], update.effective_chat.id, update.effective_user.id, reason)
        warnings = db.get_warnings(target_user['id'], update.effective_chat.id)
        
        await update.message.reply_text(
            f"⚠️ User warned!\n"
            f"👤 User: {target_user.get('first_name', 'Unknown')} (@{target_user.get('username', 'N/A')})\n"
            f"🆔 ID: {target_user['id']}\n"
            f"📝 Reason: {reason}\n"
            f"🔢 Total warnings: {len(warnings)}",
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.error(f"Error in warn_user command: {e}")
        await update.message.reply_text("❌ An error occurred while warning user!")

async def mute_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Mute a user (admin only)"""
    try:
        if not await is_approved_channel(update, context):
            return
            
        if not await is_admin(update, context):
            await update.message.reply_text("❌ This command is for admins only!")
            return
        
        if not await enforce_admin_commands(update, context):
            return
        
        target_user = await get_target_user(update, context)
        if not target_user:
            await update.message.reply_text(
                "❌ Please either:\n"
                "1. Reply to user's message\n"
                "2. Mention with @username\n"
                "3. Provide user ID"
            )
            return
        
        # Get mute duration (default: 1 hour)
        time_str = "1h"
        if len(context.args) > 0:
            if context.args[0].startswith('@'):
                if len(context.args) > 1:
                    time_str = context.args[1]
            else:
                time_str = context.args[0]
        
        mute_duration = await parse_time(time_str)
        
        if not mute_duration:
            await update.message.reply_text("❌ Invalid time format. Use like: /mute @user 1h (or 30m, 2d)")
            return
        
        until_date = datetime.now() + mute_duration
        permissions = ChatPermissions(
            can_send_messages=False,
            can_send_media_messages=False,
            can_send_polls=False,
            can_send_other_messages=False,
            can_add_web_page_previews=False,
            can_change_info=False,
            can_invite_users=False,
            can_pin_messages=False
        )
        
        try:
            await context.bot.restrict_chat_member(
                chat_id=update.effective_chat.id,
                user_id=target_user['id'],
                permissions=permissions,
                until_date=until_date
            )
            
            await update.message.reply_text(
                f"🔇 User muted!\n"
                f"👤 User: {target_user.get('first_name', 'Unknown')}\n"
                f"⏱ Duration: {time_str}\n"
                f"⏰ Until: {until_date.strftime('%Y-%m-%d %H:%M')}",
                parse_mode="Markdown"
            )
        except BadRequest as e:
            logger.error(f"Mute error: {e}")
            await update.message.reply_text("❌ Failed to mute user. Do I have the right permissions?")
    except Exception as e:
        logger.error(f"Error in mute_user command: {e}")
        await update.message.reply_text("❌ An error occurred while muting user!")

async def unmute_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Unmute a user (admin only)"""
    try:
        if not await is_approved_channel(update, context):
            return
            
        if not await is_admin(update, context):
            await update.message.reply_text("❌ This command is for admins only!")
            return
        
        if not await enforce_admin_commands(update, context):
            return
        
        target_user = await get_target_user(update, context)
        if not target_user:
            await update.message.reply_text(
                "❌ Please either:\n"
                "1. Reply to user's message\n"
                "2. Mention with @username\n"
                "3. Provide user ID"
            )
            return
        
        permissions = ChatPermissions(
            can_send_messages=True,
            can_send_media_messages=True,
            can_send_polls=True,
            can_send_other_messages=True,
            can_add_web_page_previews=True,
            can_change_info=False,
            can_invite_users=False,
            can_pin_messages=False
        )
        
        try:
            await context.bot.restrict_chat_member(
                chat_id=update.effective_chat.id,
                user_id=target_user['id'],
                permissions=permissions
            )
            await update.message.reply_text(
                f"🔊 User unmuted!\n"
                f"👤 User: {target_user.get('first_name', 'Unknown')}",
                parse_mode="Markdown"
            )
        except BadRequest as e:
            logger.error(f"Unmute error: {e}")
            await update.message.reply_text("❌ Failed to unmute user. Do I have the right permissions?")
    except Exception as e:
        logger.error(f"Error in unmute_user command: {e}")
        await update.message.reply_text("❌ An error occurred while unmuting user!")

async def kick_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Kick a user (admin only)"""
    try:
        if not await is_approved_channel(update, context):
            return
            
        if not await is_admin(update, context):
            await update.message.reply_text("❌ This command is for admins only!")
            return
        
        if not await enforce_admin_commands(update, context):
            return
        
        target_user = await get_target_user(update, context)
        if not target_user:
            await update.message.reply_text(
                "❌ Please either:\n"
                "1. Reply to user's message\n"
                "2. Mention with @username\n"
                "3. Provide user ID"
            )
            return
        
        reason = ' '.join(context.args[1:]) if len(context.args) > 1 else "No reason provided"
        
        try:
            await context.bot.ban_chat_member(
                chat_id=update.effective_chat.id,
                user_id=target_user['id'],
                until_date=datetime.now() + timedelta(minutes=1)
            )
            
            await update.message.reply_text(
                f"👢 User kicked!\n"
                f"👤 User: {target_user.get('first_name', 'Unknown')}\n"
                f"📝 Reason: {reason}",
                parse_mode="Markdown"
            )
        except BadRequest as e:
            logger.error(f"Kick error: {e}")
            await update.message.reply_text("❌ Failed to kick user. Do I have the right permissions?")
    except Exception as e:
        logger.error(f"Error in kick_user command: {e}")
        await update.message.reply_text("❌ An error occurred while kicking user!")

async def ban_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Ban a user (admin only)"""
    try:
        if not await is_approved_channel(update, context):
            return
            
        if not await is_admin(update, context):
            await update.message.reply_text("❌ This command is for admins only!")
            return
        
        if not await enforce_admin_commands(update, context):
            return
        
        target_user = await get_target_user(update, context)
        if not target_user:
            await update.message.reply_text(
                "❌ Please either:\n"
                "1. Reply to user's message\n"
                "2. Mention with @username\n"
                "3. Provide user ID"
            )
            return
        
        reason = ' '.join(context.args[1:]) if len(context.args) > 1 else "No reason provided"
        
        try:
            await context.bot.ban_chat_member(
                chat_id=update.effective_chat.id,
                user_id=target_user['id'])
            
            await update.message.reply_text(
                f"🔨 User banned!\n"
                f"👤 User: {target_user.get('first_name', 'Unknown')}\n"
                f"📝 Reason: {reason}",
                parse_mode="Markdown"
            )
        except BadRequest as e:
            logger.error(f"Ban error: {e}")
            await update.message.reply_text("❌ Failed to ban user. Do I have the right permissions?")
    except Exception as e:
        logger.error(f"Error in ban_user command: {e}")
        await update.message.reply_text("❌ An error occurred while banning user!")

async def add_money(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Add T-Money to user (admin only)"""
    try:
        if not await is_approved_channel(update, context):
            return
            
        if not await is_admin(update, context):
            await update.message.reply_text("❌ This command is for admins only!")
            return
        
        target_user = await get_target_user(update, context)
        if not target_user:
            await update.message.reply_text(
                "❌ Please either:\n"
                "1. Reply to user's message\n"
                "2. Mention with @username\n"
                "3. Provide user ID"
            )
            return
        
        if len(context.args) < 1 or not context.args[-1].isdigit():
            await update.message.reply_text("Usage: /addmoney @user <amount>")
            return
        
        amount = int(context.args[-1])
        db.add_t_money(target_user['id'], update.effective_chat.id, amount)
        user_data = db.get_user(target_user['id'], update.effective_chat.id)
        
        await update.message.reply_text(
            f"💰 Added money!\n"
            f"👤 User: {target_user.get('first_name', 'Unknown')}\n"
            f"💵 Amount: {amount}T\n"
            f"🏦 New balance: {user_data['t_money']}T",
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.error(f"Error in add_money command: {e}")
        await update.message.reply_text("❌ An error occurred while adding money!")

async def remove_money(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Remove T-Money from user (admin only)"""
    try:
        if not await is_approved_channel(update, context):
            return
            
        if not await is_admin(update, context):
            await update.message.reply_text("❌ This command is for admins only!")
            return
        
        target_user = await get_target_user(update, context)
        if not target_user:
            await update.message.reply_text(
                "❌ Please either:\n"
                "1. Reply to user's message\n"
                "2. Mention with @username\n"
                "3. Provide user ID"
            )
            return
        
        if len(context.args) < 1 or not context.args[-1].isdigit():
            await update.message.reply_text("Usage: /removemoney @user <amount>")
            return
        
        amount = int(context.args[-1])
        if db.remove_t_money(target_user['id'], update.effective_chat.id, amount):
            user_data = db.get_user(target_user['id'], update.effective_chat.id)
            await update.message.reply_text(
                f"💰 Removed money!\n"
                f"👤 User: {target_user.get('first_name', 'Unknown')}\n"
                f"💵 Amount: {amount}T\n"
                f"🏦 New balance: {user_data['t_money']}T",
                parse_mode="Markdown"
            )
        else:
            await update.message.reply_text(
                f"❌ User doesn't have enough T-Money!\n"
                f"Current balance: {db.get_balance(target_user['id'], update.effective_chat.id)}T",
                parse_mode="Markdown"
            )
    except Exception as e:
        logger.error(f"Error in remove_money command: {e}")
        await update.message.reply_text("❌ An error occurred while removing money!")

async def add_key_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Add premium key to user (admin only)"""
    try:
        if not await is_approved_channel(update, context):
            return
            
        if not await is_admin(update, context):
            await update.message.reply_text("❌ This command is for admins only!")
            return
        
        target_user = await get_target_user(update, context)
        if not target_user:
            await update.message.reply_text(
                "❌ Please either:\n"
                "1. Reply to user's message\n"
                "2. Mention with @username\n"
                "3. Provide user ID"
            )
            return
        
        if len(context.args) < 1 or not context.args[-1].isdigit():
            await update.message.reply_text("Usage: /addkey @user <days>")
            return
        
        days = int(context.args[-1])
        db.add_key(target_user['id'], update.effective_chat.id, "premium", days)
        
        await update.message.reply_text(
            f"🔑 Added premium key!\n"
            f"👤 User: {target_user.get('first_name', 'Unknown')}\n"
            f"⏳ Duration: {days} days",
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.error(f"Error in add_key_admin command: {e}")
        await update.message.reply_text("❌ An error occurred while adding key!")

async def clear_warnings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Clear user's warnings (admin only)"""
    try:
        if not await is_approved_channel(update, context):
            return
            
        if not await is_admin(update, context):
            await update.message.reply_text("❌ This command is for admins only!")
            return
        
        target_user = await get_target_user(update, context)
        if not target_user:
            await update.message.reply_text(
                "❌ Please specify user:\n"
                "1. Reply to user's message\n"
                "2. Mention with @username\n"
                "3. Provide user ID"
            )
            return
        
        db.clear_warnings(target_user['id'], update.effective_chat.id)
        await update.message.reply_text(
            f"✅ Warnings cleared!\n"
            f"👤 User: {target_user.get('first_name', 'Unknown')}",
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.error(f"Error in clear_warnings command: {e}")
        await update.message.reply_text("❌ An error occurred while clearing warnings!")

# =====================
#  NEW FEATURE COMMANDS
# =====================
async def generate_redeem_code(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Generate a redeem code (admin only)"""
    try:
        if not await is_approved_channel(update, context):
            return
            
        if not await is_admin(update, context):
            await update.message.reply_text("❌ This command is for admins only!")
            return
        
        if len(context.args) < 2 or not context.args[0].isdigit() or not context.args[1].isdigit():
            await update.message.reply_text("Usage: /gen <amount> <uses>")
            return
            
        amount = int(context.args[0])
        uses = int(context.args[1])
        
        code = generate_code()
        db.create_redeem_code(code, update.effective_chat.id, amount, uses, update.effective_user.id)
        
        await update.message.reply_text(
            f"🎟 *Redeem Code Generated* 🎟\n\n"
            f"💰 Amount: {amount}T\n"
            f"👥 Max Uses: {uses}\n"
            f"🔑 Code: `{code}`\n\n"
            "Users can redeem with /redeem",
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.error(f"Error in generate_redeem_code: {e}")
        await update.message.reply_text("❌ An error occurred while generating code!")

async def redeem_code_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Redeem a code for T-Money"""
    try:
        if not await is_approved_channel(update, context):
            return
            
        user = update.effective_user
        if not context.args or len(context.args[0]) == 0:
            await update.message.reply_text("Usage: /redeem <code>")
            return
            
        code = context.args[0].upper()
        code_data = db.get_redeem_code(code, update.effective_chat.id)
        
        if not code_data:
            await update.message.reply_text("❌ Invalid or expired code!")
            return
            
        if db.redeem_code(user.id, update.effective_chat.id, code):
            await update.message.reply_text(
                f"🎉 Code redeemed successfully!\n"
                f"💰 You received {code_data['amount']}T\n"
                f"🏦 New balance: {db.get_balance(user.id, update.effective_chat.id)}T",
                parse_mode="Markdown"
            )
        else:
            await update.message.reply_text(
                "❌ Unable to redeem code:\n"
                "- You already redeemed this code\n"
                "- Or code has reached its use limit",
                parse_mode="Markdown"
            )
    except Exception as e:
        logger.error(f"Error in redeem_code_command: {e}")
        await update.message.reply_text("❌ An error occurred while redeeming code!")

async def gift_money(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Gift T-Money to another user"""
    try:
        if not await is_approved_channel(update, context):
            return
            
        user = update.effective_user
        db.update_user(user.id, update.effective_chat.id, user.username, user.first_name, user.last_name)
        
        if len(context.args) < 2 or not context.args[-1].isdigit():
            await update.message.reply_text("Usage: /gift @user <amount>")
            return
            
        amount = int(context.args[-1])
        if amount <= 0:
            await update.message.reply_text("❌ Amount must be positive!")
            return
            
        target_user = await get_target_user(update, context)
        if not target_user:
            await update.message.reply_text(
                "❌ Please specify user:\n"
                "1. Reply to user's message\n"
                "2. Mention with @username\n"
                "3. Provide user ID"
            )
            return
            
        if target_user['id'] == user.id:
            await update.message.reply_text("❌ You can't gift yourself!")
            return
            
        if db.get_balance(user.id, update.effective_chat.id) < amount:
            await update.message.reply_text(
                f"❌ You don't have enough T-Money!\n"
                f"💵 Needed: {amount}T\n"
                f"💰 Your balance: {db.get_balance(user.id, update.effective_chat.id)}T",
                parse_mode="Markdown"
            )
            return
            
        # Perform the transaction
        if db.remove_t_money(user.id, update.effective_chat.id, amount):
            db.add_t_money(target_user['id'], update.effective_chat.id, amount)
            
            await update.message.reply_text(
                f"🎁 Gift sent!\n"
                f"👤 To: {target_user.get('first_name', 'Unknown')}\n"
                f"💰 Amount: {amount}T\n\n"
                f"💵 Your new balance: {db.get_balance(user.id, update.effective_chat.id)}T",
                parse_mode="Markdown"
            )
            
            # Notify recipient if possible
            try:
                await context.bot.send_message(
                    chat_id=target_user['id'],
                    text=f"🎁 You received a gift from {user.first_name} in {update.effective_chat.title}!\n"
                         f"💰 Amount: {amount}T\n"
                         f"🏦 New balance: {db.get_balance(target_user['id'], update.effective_chat.id)}T",
                    parse_mode="Markdown"
                )
            except Exception as e:
                logger.error(f"Couldn't notify gift recipient: {e}")
        else:
            await update.message.reply_text("❌ Transaction failed!")
    except Exception as e:
        logger.error(f"Error in gift_money: {e}")
        await update.message.reply_text("❌ An error occurred while sending gift!")

async def add_youtube_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Add YouTube video for claims (admin only)"""
    try:
        if not await is_approved_channel(update, context):
            return
            
        if not await is_admin(update, context):
            await update.message.reply_text("❌ This command is for admins only!")
            return
            
        if not context.args or len(context.args[0]) == 0:
            await update.message.reply_text("Usage: /add_yt <youtube_url>")
            return
            
        # Extract video ID from URL
        url = context.args[0]
        video_id = None
        
        # Handle different YouTube URL formats
        if "youtu.be/" in url:
            video_id = url.split("youtu.be/")[1].split("?")[0]
        elif "youtube.com/watch" in url:
            video_id = url.split("v=")[1].split("&")[0]
            
        if not video_id or len(video_id) != 11:
            await update.message.reply_text("❌ Invalid YouTube URL!")
            return
            
        if db.add_youtube_video(video_id, update.effective_chat.id, update.effective_user.id):
            await update.message.reply_text(
                f"✅ YouTube video added!\n"
                f"📺 Video ID: {video_id}\n"
                f"🔗 URL: https://youtu.be/{video_id}",
                parse_mode="Markdown"
            )
        else:
            await update.message.reply_text("❌ This video is already in the database!")
    except Exception as e:
        logger.error(f"Error in add_youtube_video: {e}")
        await update.message.reply_text("❌ An error occurred while adding video!")

async def list_youtube_videos(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """List available YouTube videos for claims"""
    try:
        if not await is_approved_channel(update, context):
            return
            
        videos = db.get_youtube_videos(update.effective_chat.id)
        if not videos:
            await update.message.reply_text("❌ No YouTube videos available for claims in this channel!")
            return
            
        response = "📺 *Available YouTube Videos for Claims* 📺\n\n"
        for i, video in enumerate(videos, 1):
            response += (
                f"{i}. https://youtu.be/{video['video_id']}\n"
                f"   Added by: {video['added_by']}\n"
                f"   Date: {video['added_at']}\n\n"
            )
            
        await update.message.reply_text(response, parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Error in list_youtube_videos: {e}")
        await update.message.reply_text("❌ An error occurred while listing videos!")

async def remove_youtube_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Remove YouTube video from claims (admin only)"""
    try:
        if not await is_approved_channel(update, context):
            return
            
        if not await is_admin(update, context):
            await update.message.reply_text("❌ This command is for admins only!")
            return
            
        if not context.args or not context.args[0].isdigit():
            await update.message.reply_text("Usage: /remove_yt <index> (use /list_yt to see indexes)")
            return
            
        index = int(context.args[0]) - 1
        videos = db.get_youtube_videos(update.effective_chat.id)
        
        if index < 0 or index >= len(videos):
            await update.message.reply_text("❌ Invalid index!")
            return
            
        video_id = videos[index]['video_id']
        if db.remove_youtube_video(video_id, update.effective_chat.id):
            await update.message.reply_text(
                f"✅ Video removed!\n"
                f"🔗 https://youtu.be/{video_id}",
                parse_mode="Markdown"
            )
        else:
            await update.message.reply_text("❌ Video not found!")
    except Exception as e:
        logger.error(f"Error in remove_youtube_video: {e}")
        await update.message.reply_text("❌ An error occurred while removing video!")

# ====================
#  MESSAGE HANDLERS
# ====================
async def message_counter(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Count user messages and check for special messages"""
    try:
        if not db.is_channel_approved(update.effective_chat.id):
            return
            
        user = update.effective_user
        if not user:
            return
        
        db.update_user(user.id, update.effective_chat.id, user.username, user.first_name, user.last_name)
        db.increment_message_count(user.id, update.effective_chat.id)
        
        # Check for birthday
        birthday = db.get_birthday(user.id, update.effective_chat.id)
        if birthday:
            today = datetime.now().strftime("%m-%d")
            if birthday == today:
                await update.message.reply_text(
                    f"🎉 Happy Birthday, {user.first_name}! 🎂\n"
                    "May your day be filled with joy and happiness!",
                    parse_mode="Markdown"
                )
        
        # Check for special message trigger
        special_msg = db.get_special_message(update.effective_chat.id)
        if special_msg and random.random() < 0.05:  # 5% chance to show special message
            user_data = db.get_user(special_msg['user_id'], update.effective_chat.id)
            await update.message.reply_text(
                f"🌟 *Special Channel Message* 🌟\n\n"
                f"{special_msg['message_text']}\n\n"
                f"📅 Set by: {user_data['first_name']}",
                parse_mode="Markdown"
            )
    except Exception as e:
        logger.error(f"Error in message_counter: {e}")

async def new_member(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Welcome new members"""
    try:
        if not db.is_channel_approved(update.effective_chat.id):
            return
            
        for user in update.message.new_chat_members:
            if user.is_bot:
                continue
            
            db.update_user(user.id, update.effective_chat.id, user.username, user.first_name, user.last_name)
            await update.message.reply_text(
                f"👋 Welcome to the channel, {user.first_name}!\n"
                "Type /help to see what I can do!",
                parse_mode="Markdown"
            )
    except Exception as e:
        logger.error(f"Error in new_member handler: {e}")

async def left_member(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle when a member leaves"""
    try:
        if not db.is_channel_approved(update.effective_chat.id):
            return
            
        user = update.message.left_chat_member
        if user.is_bot:
            return
        
        await update.message.reply_text(
            f"👋 Goodbye, {user.first_name}! We'll miss you!",
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.error(f"Error in left_member handler: {e}")

async def check_mentions(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Check if the bot is mentioned"""
    try:
        if not db.is_channel_approved(update.effective_chat.id):
            return
            
        if context.bot.username.lower() in update.message.text.lower():
            await update.message.reply_text(
                "👋 You mentioned me! How can I help?\n"
                "Type /help to see my commands.",
                parse_mode="Markdown"
            )
    except Exception as e:
        logger.error(f"Error in check_mentions handler: {e}")

def main() -> None:
    """Start the bot."""
    # Create the Application
    application = Application.builder().token(BOT_TOKEN).build()

    # Command handlers
    command_handlers = [
        # Basic commands
        CommandHandler("start", start),
        CommandHandler("help", help),
        CommandHandler("info", info_user),
        CommandHandler("id", id_command),
        CommandHandler("rank", rank),
        CommandHandler("top", top),
        
        # Economy commands
        CommandHandler("daily", daily),
        CommandHandler("claim_yt", claim_yt),
        CommandHandler("balance", info_user),  # Alias for info
        CommandHandler("buykey", buy_key),
        CommandHandler("mykeys", my_keys),
        CommandHandler("redeem", redeem_code_command),
        CommandHandler("gift", gift_money),
        
        # Social features
        CommandHandler("setbirthday", set_birthday),
        CommandHandler("birthday", show_birthday),
        CommandHandler("specialmsg", special_message),
        CommandHandler("set_specialmsg", set_special_message),
        CommandHandler("del_specialmsg", del_special_message),
        CommandHandler("announcement", announcement),
        
        # Admin commands
        CommandHandler("warn", warn_user),
        CommandHandler("mute", mute_user),
        CommandHandler("unmute", unmute_user),
        CommandHandler("kick", kick_user),
        CommandHandler("ban", ban_user),
        CommandHandler("addmoney", add_money),
        CommandHandler("removemoney", remove_money),
        CommandHandler("addkey", add_key_admin),
        CommandHandler("clearwarns", clear_warnings),
        CommandHandler("admins", admins_command),
        CommandHandler("gen", generate_redeem_code),
        CommandHandler("add_yt", add_youtube_video),
        CommandHandler("list_yt", list_youtube_videos),
        CommandHandler("remove_yt", remove_youtube_video),
        
        # Developer command
        CommandHandler("approve_channel", approve_channel),
    ]

    # Message handlers
    message_handlers = [
        MessageHandler(filters.TEXT & ~filters.COMMAND, message_counter),
        MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, new_member),
        MessageHandler(filters.StatusUpdate.LEFT_CHAT_MEMBER, left_member),
        MessageHandler(filters.TEXT & filters.Entity("mention"), check_mentions)
    ]

    # Register all handlers
    for handler in command_handlers + message_handlers:
        application.add_handler(handler)
    
    # Callback handler
    application.add_handler(CallbackQueryHandler(yt_confirmation, pattern="^yt_confirm_"))
    
    # Error handler
    application.add_error_handler(error_handler)

    # Start the bot
    logger.info("Starting bot...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()