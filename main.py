"""
=============================================================================
🏛️ CAMPUS STRANGER / FRIEND FINDER TELEGRAM BOT (OMEGLE-STYLE)
Built with: python-telegram-bot v20+ (Async), asyncpg / sqlite3, aiohttp
=============================================================================
Features:
- Anonymous 1-on-1 chatting between campus students
- Queue matching with common interest discovery
- Safe profile reveal system (both must agree before sharing handles)
- Campus meetup spot suggestions & icebreakers (/meet)
- Fast skip (/next) and disconnect (/stop)
- Student safety: report & instant block system (/report)
- Database: Free Neon / Supabase PostgreSQL with SQLite automatic fallback
=============================================================================
"""

import os
import sys
import logging
import asyncio
import random
import sqlite3
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import Optional, Dict, Set, Tuple
from datetime import datetime

# Telegram Bot Imports
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardRemove
)
from telegram.ext import (
    Application,
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ConversationHandler,
    ContextTypes,
    filters
)

# Optional asyncpg for PostgreSQL (Neon, Supabase, Render, Railway, etc.)
try:
    import asyncpg
    HAS_ASYNCPG = True
except ImportError:
    HAS_ASYNCPG = False

# ---------------------------------------------------------------------------
# LOGGING CONFIGURATION
# ---------------------------------------------------------------------------
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# CONFIGURATION & ENVIRONMENT VARIABLES
# ---------------------------------------------------------------------------
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
DATABASE_URL = os.getenv("DATABASE_URL", "").strip()
ADMIN_USER_ID = int(os.getenv("ADMIN_USER_ID", "0"))
UNIVERSITY_NAME = os.getenv("UNIVERSITY_NAME", "Campus")

# List of physical campus spots for meetup suggestions
CAMPUS_SPOTS = [
    "Student Union Cafe",
    "Main Library 2nd Floor Lounge",
    "Campus Green / Quad Bench",
    "Engineering Hall Atrium",
    "Campus Coffee Shop",
    "Dorm Courtyard",
    "Recreation Center Plaza",
    "Science Building Breezeway"
]

ICEBREAKERS = [
    "What's your favorite study spot on campus when you actually need to focus?",
    "What's the best cheap food spot near campus?",
    "What's the hardest class you've taken here so far?",
    "Are you a morning lecture person or an 8 PM library grinder?",
    "If you could change one thing about our campus, what would it be?",
    "What's your go-to caffeine order during finals week?",
    "Which professor here has the most chaotic energy?",
    "Are you involved in any campus clubs or sports?",
    "What's the most underrated spot on campus?",
    "What is your dream post-grad career?"
]

INTERESTS_LIST = [
    "☕ Coffee & Boba", "💻 Coding & Tech", "🎮 Gaming & Esports",
    "📚 Study Buddy", "🏋️ Gym & Fitness", "🎨 Art & Design",
    "🎵 Music & Concerts", "🍜 Foodies", "🍿 Movies & Anime",
    "🌿 Outdoors & Hiking", "📸 Photography", "⚽ Campus Sports"
]

YEAR_OPTIONS = ["Freshman (1st)", "Sophomore (2nd)", "Junior (3rd)", "Senior (4th)", "Grad / Master / PhD"]

# ---------------------------------------------------------------------------
# CONVERSATION STATES (FOR ONBOARDING PROFILE SETUP)
# ---------------------------------------------------------------------------
STATE_NAME, STATE_MAJOR, STATE_YEAR, STATE_DORM, STATE_INTERESTS, STATE_HANDLE = range(6)

# ---------------------------------------------------------------------------
# IN-MEMORY ACTIVE CHAT ROUTER & MATCHING QUEUE
# ---------------------------------------------------------------------------
# Active matches: user_id -> partner_id
active_chats: Dict[int, int] = {}
# Waiting queue of user_ids
waiting_queue: Set[int] = set()
# Reveal proposals: user_id -> set of agreed user_ids
reveal_requests: Dict[int, Set[int]] = {}
# Blocklist: user_id -> set of blocked partner_ids
blocked_pairs: Dict[int, Set[int]] = {}


# ---------------------------------------------------------------------------
# DATABASE MANAGER (PostgreSQL & SQLite Seamless Support)
# ---------------------------------------------------------------------------
class DatabaseManager:
    def __init__(self, db_url: str):
        self.db_url = db_url
        self.is_postgres = db_url.startswith("postgres://") or db_url.startswith("postgresql://")
        self.pg_pool = None
        self.sqlite_file = "campus_bot.db"

    async def init_db(self):
        """Initialize database schema on startup."""
        if self.is_postgres and HAS_ASYNCPG:
            try:
                fixed_url = self.db_url.replace("postgres://", "postgresql://")
                self.pg_pool = await asyncpg.create_pool(fixed_url, max_size=10)
                async with self.pg_pool.acquire() as conn:
                    await conn.execute("""
                        CREATE TABLE IF NOT EXISTS students (
                            user_id BIGINT PRIMARY KEY,
                            username TEXT,
                            full_name TEXT,
                            major TEXT,
                            study_year TEXT,
                            dorm TEXT,
                            interests TEXT,
                            bio TEXT,
                            social_handle TEXT,
                            is_banned BOOLEAN DEFAULT FALSE,
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            total_chats INT DEFAULT 0
                        );
                        CREATE TABLE IF NOT EXISTS chat_logs (
                            id SERIAL PRIMARY KEY,
                            user_1 BIGINT,
                            user_2 BIGINT,
                            started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            ended_at TIMESTAMP
                        );
                        CREATE TABLE IF NOT EXISTS reports (
                            id SERIAL PRIMARY KEY,
                            reporter_id BIGINT,
                            reported_id BIGINT,
                            reason TEXT,
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                        );
                    """)
                logger.info(" Connected to PostgreSQL Database successfully.")
                return
            except Exception as e:
                logger.error(f" PostgreSQL connection failed: {e}. Falling back to SQLite.")
                self.is_postgres = False

        # SQLite Fallback
        conn = sqlite3.connect(self.sqlite_file)
        cur = conn.cursor()
        cur.executescript("""
            CREATE TABLE IF NOT EXISTS students (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                full_name TEXT,
                major TEXT,
                study_year TEXT,
                dorm TEXT,
                interests TEXT,
                bio TEXT,
                social_handle TEXT,
                is_banned INTEGER DEFAULT 0,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                total_chats INTEGER DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS chat_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_1 INTEGER,
                user_2 INTEGER,
                started_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                ended_at DATETIME
            );
            CREATE TABLE IF NOT EXISTS reports (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                reporter_id INTEGER,
                reported_id INTEGER,
                reason TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );
        """)
        conn.commit()
        conn.close()
        logger.info(f" Initialized SQLite Database at {self.sqlite_file}.")

    async def get_user(self, user_id: int) -> Optional[dict]:
        """Fetch student profile by telegram user_id."""
        if self.is_postgres and self.pg_pool:
            async with self.pg_pool.acquire() as conn:
                row = await conn.fetchrow("SELECT * FROM students WHERE user_id = $1", user_id)
                return dict(row) if row else None
        else:
            conn = sqlite3.connect(self.sqlite_file)
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            cur.execute("SELECT * FROM students WHERE user_id = ?", (user_id,))
            row = cur.fetchone()
            res = dict(row) if row else None
            conn.close()
            return res

    async def save_user(self, data: dict):
        """Save or update student profile."""
        user_id = data["user_id"]
        username = data.get("username", "")
        name = data.get("name", "Fellow Student")
        major = data.get("major", "Undeclared")
        year = data.get("year", "Undergrad")
        dorm = data.get("dorm", "Campus")
        interests = ",".join(data.get("interests", [])) if isinstance(data.get("interests"), list) else data.get("interests", "")
        bio = data.get("bio", "Hey! Excited to meet people around campus.")
        handle = data.get("social_handle", f"@{username}" if username else "Not shared")

        if self.is_postgres and self.pg_pool:
            async with self.pg_pool.acquire() as conn:
                await conn.execute("""
                    INSERT INTO students (user_id, username, full_name, major, study_year, dorm, interests, bio, social_handle)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                    ON CONFLICT (user_id) DO UPDATE SET
                        username = EXCLUDED.username,
                        full_name = EXCLUDED.full_name,
                        major = EXCLUDED.major,
                        study_year = EXCLUDED.study_year,
                        dorm = EXCLUDED.dorm,
                        interests = EXCLUDED.interests,
                        bio = EXCLUDED.bio,
                        social_handle = EXCLUDED.social_handle;
                """, user_id, username, name, major, year, dorm, interests, bio, handle)
        else:
            conn = sqlite3.connect(self.sqlite_file)
            cur = conn.cursor()
            cur.execute("""
                INSERT OR REPLACE INTO students (user_id, username, full_name, major, study_year, dorm, interests, bio, social_handle)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (user_id, username, name, major, year, dorm, interests, bio, handle))
            conn.commit()
            conn.close()

    async def increment_chat_count(self, user1: int, user2: int):
        """Update student stats."""
        if self.is_postgres and self.pg_pool:
            async with self.pg_pool.acquire() as conn:
                await conn.execute("UPDATE students SET total_chats = total_chats + 1 WHERE user_id IN ($1, $2)", user1, user2)
                await conn.execute("INSERT INTO chat_logs (user_1, user_2) VALUES ($1, $2)", user1, user2)
        else:
            conn = sqlite3.connect(self.sqlite_file)
            cur = conn.cursor()
            cur.execute("UPDATE students SET total_chats = total_chats + 1 WHERE user_id IN (?, ?)", (user1, user2))
            cur.execute("INSERT INTO chat_logs (user_1, user_2) VALUES (?, ?)", (user1, user2))
            conn.commit()
            conn.close()

    async def log_report(self, reporter_id: int, reported_id: int, reason: str):
        """Log safety report."""
        if self.is_postgres and self.pg_pool:
            async with self.pg_pool.acquire() as conn:
                await conn.execute("INSERT INTO reports (reporter_id, reported_id, reason) VALUES ($1, $2, $3)", reporter_id, reported_id, reason)
        else:
            conn = sqlite3.connect(self.sqlite_file)
            cur = conn.cursor()
            cur.execute("INSERT INTO reports (reporter_id, reported_id, reason) VALUES (?, ?, ?)", (reporter_id, reported_id, reason))
            conn.commit()
            conn.close()


db = DatabaseManager(DATABASE_URL)

# ---------------------------------------------------------------------------
# UI KEYBOARDS & HELPERS
# ---------------------------------------------------------------------------
def get_main_menu_keyboard() -> ReplyKeyboardMarkup:
    """Persistent action buttons while in the main menu."""
    keyboard = [
        [KeyboardButton("🔍 Find Campus Stranger"), KeyboardButton("👤 My Student Profile")],
        [KeyboardButton("🎯 Common Interest Match"), KeyboardButton("❓ Help & Rules")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def get_in_chat_keyboard() -> ReplyKeyboardMarkup:
    """Action buttons while connected to a stranger."""
    keyboard = [
        [KeyboardButton("⏭️ Next Stranger"), KeyboardButton("🛑 End Chat")],
        [KeyboardButton("🤝 Reveal Profile / Swap Socials"), KeyboardButton("📍 Suggest Campus Spot")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

# ---------------------------------------------------------------------------
# MATCHING ENGINE
# ---------------------------------------------------------------------------
async def match_user(user_id: int, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Try to pair user_id with another student waiting in the queue."""
    user_blocks = blocked_pairs.get(user_id, set())

    # Find candidates not blocked and not self
    candidates = [uid for uid in waiting_queue if uid != user_id and uid not in user_blocks and user_id not in blocked_pairs.get(uid, set())]

    if not candidates:
        waiting_queue.add(user_id)
        return False

    # Pick a partner
    partner_id = random.choice(candidates)
    waiting_queue.remove(partner_id)

    # Establish bidirectional link
    active_chats[user_id] = partner_id
    active_chats[partner_id] = user_id

    # Reset reveal requests for both
    reveal_requests[user_id] = set()
    reveal_requests[partner_id] = set()

    # Fetch user profiles to find common ground
    p1 = await db.get_user(user_id)
    p2 = await db.get_user(partner_id)

    common_interests = []
    if p1 and p2 and p1.get("interests") and p2.get("interests"):
        i1 = set([x.strip() for x in p1["interests"].split(",") if x.strip()])
        i2 = set([x.strip() for x in p2["interests"].split(",") if x.strip()])
        common_interests = list(i1.intersection(i2))

    # Shared greeting info
    info_text = f"🎉 <b>Connected to a fellow {UNIVERSITY_NAME} student!</b>\n\n"
    if common_interests:
        info_text += f"✨ <i>Common interests:</i> {', '.join(common_interests)}\n"
    else:
        info_text += "💬 Say hello and break the ice! Everything is anonymous until you both choose to reveal.\n"
    
    info_text += "\n<i>Tip: Tap [🤝 Reveal Profile] when you want to exchange Telegram/IG handles and meet up on campus!</i>"

    # Send notifications to both
    try:
        await context.bot.send_message(
            chat_id=user_id,
            text=info_text,
            parse_mode="HTML",
            reply_markup=get_in_chat_keyboard()
        )
    except Exception as e:
        logger.error(f"Failed to send match alert to {user_id}: {e}")

    try:
        await context.bot.send_message(
            chat_id=partner_id,
            text=info_text,
            parse_mode="HTML",
            reply_markup=get_in_chat_keyboard()
        )
    except Exception as e:
        logger.error(f"Failed to send match alert to {partner_id}: {e}")

    await db.increment_chat_count(user_id, partner_id)
    return True


async def disconnect_chat(user_id: int, context: ContextTypes.DEFAULT_TYPE, notify_partner: bool = True, reason: str = "Partner left"):
    """Disconnect active pair."""
    partner_id = active_chats.pop(user_id, None)
    if partner_id:
        active_chats.pop(partner_id, None)
        if notify_partner:
            try:
                await context.bot.send_message(
                    chat_id=partner_id,
                    text=f"👋 <b>Your chat partner has disconnected.</b> ({reason})\n\nTap below to find someone new on campus!",
                    parse_mode="HTML",
                    reply_markup=get_main_menu_keyboard()
                )
            except Exception as e:
                logger.error(f"Error notifying partner {partner_id}: {e}")

    # Remove any reveal tokens
    reveal_requests.pop(user_id, None)
    if partner_id:
        reveal_requests.pop(partner_id, None)


# ---------------------------------------------------------------------------
# COMMAND HANDLERS
# ---------------------------------------------------------------------------
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command. Check registration."""
    user = update.effective_user
    db_user = await db.get_user(user.id)

    if not db_user:
        welcome_text = (
            f"👋 Welcome to <b>{UNIVERSITY_NAME} Stranger & Friend Finder</b>! 🏛️\n\n"
            f"Connect 1-on-1 with random students across campus anonymously. "
            f"Chat, discover common majors and hobbies, and swap social handles when you're ready to grab coffee or study together!\n\n"
            f"Let's set up your quick student profile first (takes 20 seconds) 👇"
        )
        keyboard = [[InlineKeyboardButton("🚀 Create Student Profile", callback_data="start_onboarding")]]
        await update.message.reply_text(
            welcome_text,
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    else:
        await update.message.reply_text(
            f"Welcome back, <b>{db_user.get('full_name', 'Student')}</b>! 🎓\n\n"
            f"Ready to meet someone new around campus?",
            parse_mode="HTML",
            reply_markup=get_main_menu_keyboard()
        )


async def find_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start searching for a campus stranger."""
    user_id = update.effective_user.id
    db_user = await db.get_user(user_id)

    if not db_user:
        await update.message.reply_text(
            "⚠️ Please complete your student profile first with /profile or /start to start matching!",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("📝 Setup Profile", callback_data="start_onboarding")]])
        )
        return

    if user_id in active_chats:
        await update.message.reply_text(
            "⚠️ You are already in an active chat! Use /next to find someone else or /stop to end it.",
            reply_markup=get_in_chat_keyboard()
        )
        return

    if user_id in waiting_queue:
        await update.message.reply_text("⏳ You are already in the queue. Looking for a campus match...")
        return

    await update.message.reply_text(
        f"🔍 <b>Searching for an active student at {UNIVERSITY_NAME}...</b>\n"
        "Hang tight, you'll be connected in moments! ⏳\n\n"
        "<i>Send /stop at any time to cancel queue.</i>",
        parse_mode="HTML"
    )

    matched = await match_user(user_id, context)
    if not matched:
        logger.info(f"User {user_id} added to waiting queue (Current queue size: {len(waiting_queue)})")


async def next_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Disconnect current stranger and immediately find a new one."""
    user_id = update.effective_user.id
    if user_id in active_chats:
        await disconnect_chat(user_id, context, notify_partner=True, reason="Partner skipped to /next")
        await update.message.reply_text("⏭️ <b>Skipped to next!</b> Searching for a new student...", parse_mode="HTML")
        await match_user(user_id, context)
    elif user_id in waiting_queue:
        await update.message.reply_text("⏳ Still looking for a student in queue...")
    else:
        await find_command(update, context)


async def stop_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Stop active chat or leave queue."""
    user_id = update.effective_user.id
    if user_id in waiting_queue:
        waiting_queue.remove(user_id)
        await update.message.reply_text("🛑 <b>Left the search queue.</b>", parse_mode="HTML", reply_markup=get_main_menu_keyboard())
        return

    if user_id in active_chats:
        await disconnect_chat(user_id, context, notify_partner=True, reason="Partner ended the chat")
        await update.message.reply_text("🛑 <b>Chat ended.</b> Hope you had a nice talk!", parse_mode="HTML", reply_markup=get_main_menu_keyboard())
        return

    await update.message.reply_text("You are not in any active chat.", reply_markup=get_main_menu_keyboard())


async def reveal_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Propose social profile swap."""
    user_id = update.effective_user.id
    if user_id not in active_chats:
        await update.message.reply_text("⚠️ You must be in an active chat with a student to exchange profiles.")
        return

    partner_id = active_chats[user_id]
    user_reveals = reveal_requests.setdefault(user_id, set())
    user_reveals.add(partner_id)

    partner_reveals = reveal_requests.get(partner_id, set())

    if user_id in partner_reveals:
        # BOTH AGREED! Exchange profiles!
        p1 = await db.get_user(user_id)
        p2 = await db.get_user(partner_id)

        msg_for_user = (
            "🎉 <b>MUTUAL REVEAL SUCCESSFUL!</b> 🤝\n\n"
            f"Here is your partner's student profile:\n"
            f"👤 <b>Name:</b> {p2.get('full_name', 'Student')}\n"
            f"📚 <b>Major:</b> {p2.get('major', 'N/A')} ({p2.get('study_year', 'N/A')})\n"
            f"🏢 <b>Dorm/Campus:</b> {p2.get('dorm', 'N/A')}\n"
            f"✨ <b>Interests:</b> {p2.get('interests', 'N/A')}\n"
            f"📝 <b>Bio:</b> {p2.get('bio', '')}\n\n"
            f"🔗 <b>Contact / Social Handle:</b> {p2.get('social_handle', 'N/A')}\n\n"
            f"<i>You can now reach out directly or propose a spot to meet via /meet!</i>"
        )

        msg_for_partner = (
            "🎉 <b>MUTUAL REVEAL SUCCESSFUL!</b> 🤝\n\n"
            f"Here is your partner's student profile:\n"
            f"👤 <b>Name:</b> {p1.get('full_name', 'Student')}\n"
            f"📚 <b>Major:</b> {p1.get('major', 'N/A')} ({p1.get('study_year', 'N/A')})\n"
            f"🏢 <b>Dorm/Campus:</b> {p1.get('dorm', 'N/A')}\n"
            f"✨ <b>Interests:</b> {p1.get('interests', 'N/A')}\n"
            f"📝 <b>Bio:</b> {p1.get('bio', '')}\n\n"
            f"🔗 <b>Contact / Social Handle:</b> {p1.get('social_handle', 'N/A')}\n\n"
            f"<i>You can now reach out directly or propose a spot to meet via /meet!</i>"
        )

        await context.bot.send_message(chat_id=user_id, text=msg_for_user, parse_mode="HTML")
        await context.bot.send_message(chat_id=partner_id, text=msg_for_partner, parse_mode="HTML")
    else:
        await update.message.reply_text("⏳ <b>Reveal request sent!</b> Waiting for your chat partner to accept...", parse_mode="HTML")
        
        keyboard = [
            [
                InlineKeyboardButton("✅ Accept Profile Swap", callback_data="accept_reveal"),
                InlineKeyboardButton("❌ Decline", callback_data="decline_reveal")
            ]
        ]
        await context.bot.send_message(
            chat_id=partner_id,
            text="🤝 <b>Your chat partner proposed to swap student profiles & social handles!</b>\n\nDo you accept?",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )


async def meet_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Suggest random campus spot and icebreaker."""
    user_id = update.effective_user.id
    if user_id not in active_chats:
        await update.message.reply_text("⚠️ Connect with a student first using /find!")
        return

    partner_id = active_chats[user_id]
    spot = random.choice(CAMPUS_SPOTS)
    icebreaker = random.choice(ICEBREAKERS)

    text = (
        f"📍 <b>Campus Meetup Suggestion</b>\n\n"
        f"🏛️ <b>Spot:</b> {spot}\n"
        f"💡 <b>Icebreaker Question:</b> <i>\"{icebreaker}\"</i>\n\n"
        f"<i>Want to meet there? Ask your partner or tap /reveal to exchange socials!</i>"
    )

    await update.message.reply_text(text, parse_mode="HTML")
    await context.bot.send_message(chat_id=partner_id, text=text, parse_mode="HTML")


async def report_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Report and block stranger."""
    user_id = update.effective_user.id
    if user_id not in active_chats:
        await update.message.reply_text("⚠️ You can only report someone during an active chat.")
        return

    partner_id = active_chats[user_id]
    blocked_pairs.setdefault(user_id, set()).add(partner_id)
    blocked_pairs.setdefault(partner_id, set()).add(user_id)

    await disconnect_chat(user_id, context, notify_partner=True, reason="Partner reported & ended chat")
    await db.log_report(user_id, partner_id, "Inappropriate chat report")

    await update.message.reply_text(
        "🛡️ <b>User reported and permanently blocked.</b> You will never be matched with them again.\n\nSearching for a new student...",
        parse_mode="HTML"
    )
    await match_user(user_id, context)


async def profile_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show current student profile."""
    user_id = update.effective_user.id
    p = await db.get_user(user_id)
    if not p:
        await update.message.reply_text("No profile found. Use /start to create one.")
        return

    text = (
        f"🎓 <b>Your {UNIVERSITY_NAME} Profile</b>\n\n"
        f"👤 <b>Name:</b> {p.get('full_name')}\n"
        f"📚 <b>Major:</b> {p.get('major')} ({p.get('study_year')})\n"
        f"🏢 <b>Dorm/Area:</b> {p.get('dorm')}\n"
        f"✨ <b>Interests:</b> {p.get('interests')}\n"
        f"📝 <b>Bio:</b> {p.get('bio')}\n"
        f"🔗 <b>Handle:</b> {p.get('social_handle')}\n"
        f"📊 <b>Total Chats:</b> {p.get('total_chats', 0)}"
    )
    keyboard = [[InlineKeyboardButton("✏️ Edit Profile", callback_data="start_onboarding")]]
    await update.message.reply_text(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(keyboard))


# ---------------------------------------------------------------------------
# MESSAGE RELAY (ANONYMOUS CHAT BRIDGE)
# ---------------------------------------------------------------------------
async def relay_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Relay user message to connected stranger anonymously."""
    user_id = update.effective_user.id
    text = update.message.text if update.message else ""

    # Check for Quick Keyboard text triggers
    if text == "🔍 Find Campus Stranger" or text == "🎯 Common Interest Match":
        await find_command(update, context)
        return
    elif text == "⏭️ Next Stranger":
        await next_command(update, context)
        return
    elif text == "🛑 End Chat":
        await stop_command(update, context)
        return
    elif text == "🤝 Reveal Profile / Swap Socials":
        await reveal_command(update, context)
        return
    elif text == "📍 Suggest Campus Spot":
        await meet_command(update, context)
        return
    elif text == "👤 My Student Profile":
        await profile_command(update, context)
        return
    elif text == "❓ Help & Rules":
        await update.message.reply_text(
            f"📖 <b>{UNIVERSITY_NAME} Bot Rules & Help</b>\n\n"
            "1. <b>Be Respectful:</b> Treat fellow students with kindness.\n"
            "2. <b>Anonymous First:</b> Your name & handle are hidden until you both tap /reveal.\n"
            "3. <b>Physical Meetups:</b> Always meet in public campus areas (Library, Student Union, Campus Cafes).\n"
            "4. <b>Safety:</b> Use /report immediately if someone behaves inappropriately.\n\n"
            "<b>Commands:</b>\n"
            "/find - Find a stranger\n"
            "/next - Skip to next student\n"
            "/stop - Stop chatting\n"
            "/reveal - Exchange profiles & socials\n"
            "/meet - Campus spot & icebreaker\n"
            "/profile - View your profile",
            parse_mode="HTML"
        )
        return

    # Check if user is in an active chat
    if user_id not in active_chats:
        if user_id in waiting_queue:
            await update.message.reply_text("⏳ You are still in queue. We'll connect you as soon as another student searches!")
        else:
            await update.message.reply_text(
                "💬 You are not in a chat right now. Tap <b>🔍 Find Campus Stranger</b> below to start!",
                parse_mode="HTML",
                reply_markup=get_main_menu_keyboard()
            )
        return

    partner_id = active_chats[user_id]

    # Forward message types anonymously
    try:
        if update.message.text:
            await context.bot.send_message(chat_id=partner_id, text=update.message.text)
        elif update.message.photo:
            photo_file_id = update.message.photo[-1].file_id
            caption = update.message.caption or ""
            await context.bot.send_photo(chat_id=partner_id, photo=photo_file_id, caption=caption)
        elif update.message.animation:
            caption = update.message.caption or ""
            await context.bot.send_animation(chat_id=partner_id, animation=update.message.animation.file_id, caption=caption)
        elif update.message.video:
            caption = update.message.caption or ""
            await context.bot.send_video(chat_id=partner_id, video=update.message.video.file_id, caption=caption)
        elif update.message.voice:
            await context.bot.send_voice(chat_id=partner_id, voice=update.message.voice.file_id)
        elif update.message.audio:
            caption = update.message.caption or ""
            await context.bot.send_audio(chat_id=partner_id, audio=update.message.audio.file_id, caption=caption)
        elif update.message.document:
            caption = update.message.caption or ""
            await context.bot.send_document(chat_id=partner_id, document=update.message.document.file_id, caption=caption)
        elif update.message.sticker:
            await context.bot.send_sticker(chat_id=partner_id, sticker=update.message.sticker.file_id)
        elif update.message.video_note:
            await context.bot.send_video_note(chat_id=partner_id, video_note=update.message.video_note.file_id)
        else:
            await update.message.reply_text("ℹ️ This media format is not supported for anonymous relay.")
    except Exception as e:
        logger.error(f"Error relaying message from {user_id} to {partner_id}: {e}")
        await update.message.reply_text("⚠️ Could not deliver message. Your partner might have disconnected.")
        await disconnect_chat(user_id, context, notify_partner=False)


# ---------------------------------------------------------------------------
# ONBOARDING CONVERSATION FLOW
# ---------------------------------------------------------------------------
async def start_onboarding_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data["onboarding"] = {}
    await query.edit_message_text("🎓 Step 1/5: What is your <b>First Name</b> or Nickname on campus?", parse_mode="HTML")
    return STATE_NAME

async def onboarding_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["onboarding"]["name"] = update.message.text.strip()
    await update.message.reply_text("📚 Step 2/5: What is your <b>Major / Faculty</b>? (e.g. Computer Science, Business, Biology, Arts)", parse_mode="HTML")
    return STATE_MAJOR

async def onboarding_major(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["onboarding"]["major"] = update.message.text.strip()
    
    keyboard = [[KeyboardButton(y)] for y in YEAR_OPTIONS]
    await update.message.reply_text(
        "📅 Step 3/5: What is your <b>Academic Year</b>?",
        parse_mode="HTML",
        reply_markup=ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
    )
    return STATE_YEAR

async def onboarding_year(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["onboarding"]["year"] = update.message.text.strip()
    await update.message.reply_text(
        "🏢 Step 4/5: What is your <b>Campus / Dorm / Area</b>? (e.g. North Dorms, Off-Campus West, Engineering Quad)",
        parse_mode="HTML",
        reply_markup=ReplyKeyboardRemove()
    )
    return STATE_DORM

async def onboarding_dorm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["onboarding"]["dorm"] = update.message.text.strip()
    
    await update.message.reply_text(
        "✨ Step 5/5: Type 2 to 4 of your <b>Interests & Hobbies</b> separated by commas.\n\n"
        "<i>Examples: Coffee, Coding, Gaming, Gym, Anime, Study Buddies</i>",
        parse_mode="HTML"
    )
    return STATE_INTERESTS

async def onboarding_interests(update: Update, context: ContextTypes.DEFAULT_TYPE):
    raw = update.message.text.strip()
    interests = [x.strip() for x in raw.split(",") if x.strip()]
    context.user_data["onboarding"]["interests"] = interests
    
    user = update.effective_user
    default_handle = f"@{user.username}" if user.username else "Will share manually"

    await update.message.reply_text(
        f"🔗 What is your <b>Telegram Username or Instagram Handle</b> to exchange when you mutually reveal?\n\n"
        f"(Default: <code>{default_handle}</code> or type custom):",
        parse_mode="HTML"
    )
    return STATE_HANDLE

async def onboarding_handle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    handle = update.message.text.strip()
    context.user_data["onboarding"]["social_handle"] = handle
    
    user = update.effective_user
    data = context.user_data["onboarding"]
    data["user_id"] = user.id
    data["username"] = user.username or ""

    await db.save_user(data)

    await update.message.reply_text(
        f"🎉 <b>Profile Created Successfully!</b>\n\n"
        f"You are all set to find new friends across {UNIVERSITY_NAME}! 🏛️\n"
        f"Tap <b>🔍 Find Campus Stranger</b> below to start your first chat.",
        parse_mode="HTML",
        reply_markup=get_main_menu_keyboard()
    )
    return ConversationHandler.END


async def cancel_onboarding(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Profile setup cancelled.", reply_markup=get_main_menu_keyboard())
    return ConversationHandler.END


# ---------------------------------------------------------------------------
# CALLBACK QUERY HANDLER (FOR REVEAL & BUTTONS)
# ---------------------------------------------------------------------------
async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    user_id = query.from_user.id

    if data == "accept_reveal":
        if user_id not in active_chats:
            await query.edit_message_text("⚠️ Chat already ended.")
            return

        partner_id = active_chats[user_id]
        reveal_requests.setdefault(user_id, set()).add(partner_id)
        
        await query.edit_message_text("✅ Accepted! Exchanging profiles...")
        
        p1 = await db.get_user(user_id)
        p2 = await db.get_user(partner_id)

        msg1 = (
            "🎉 <b>MUTUAL PROFILE REVEAL!</b> 🤝\n\n"
            f"👤 <b>Name:</b> {p2.get('full_name')}\n"
            f"📚 <b>Major:</b> {p2.get('major')} ({p2.get('study_year')})\n"
            f"🏢 <b>Dorm:</b> {p2.get('dorm')}\n"
            f"✨ <b>Interests:</b> {p2.get('interests')}\n"
            f"🔗 <b>Contact Handle:</b> {p2.get('social_handle')}\n\n"
            f"<i>Say hi or suggest a campus spot with /meet!</i>"
        )
        msg2 = (
            "🎉 <b>MUTUAL PROFILE REVEAL!</b> 🤝\n\n"
            f"👤 <b>Name:</b> {p1.get('full_name')}\n"
            f"📚 <b>Major:</b> {p1.get('major')} ({p1.get('study_year')})\n"
            f"🏢 <b>Dorm:</b> {p1.get('dorm')}\n"
            f"✨ <b>Interests:</b> {p1.get('interests')}\n"
            f"🔗 <b>Contact Handle:</b> {p1.get('social_handle')}\n\n"
            f"<i>Say hi or suggest a campus spot with /meet!</i>"
        )
        await context.bot.send_message(chat_id=user_id, text=msg1, parse_mode="HTML")
        await context.bot.send_message(chat_id=partner_id, text=msg2, parse_mode="HTML")

    elif data == "decline_reveal":
        await query.edit_message_text("❌ You declined the profile exchange. The chat remains 100% anonymous.")


# ---------------------------------------------------------------------------
# LIGHTWEIGHT HTTP HEALTH SERVER (FOR RENDER / CLOUD HOSTING)
# ---------------------------------------------------------------------------
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain")
        self.end_headers()
        self.wfile.write(b"OK - Campus Telegram Bot is running!\n")

    def log_message(self, format, *args):
        # Suppress noisy HTTP health log polling
        pass


def start_health_server():
    """Starts a lightweight HTTP server if $PORT is assigned by Render or cloud host."""
    port_str = os.getenv("PORT")
    if port_str:
        try:
            port = int(port_str)
            server = HTTPServer(("0.0.0.0", port), HealthCheckHandler)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            logger.info(f"🌐 Cloud Health Check server listening on 0.0.0.0:{port} (Render / Cloud Web Service compatible)")
        except Exception as e:
            logger.warning(f"Could not start HTTP health server on port {port_str}: {e}")


# ---------------------------------------------------------------------------
# MAIN APPLICATION STARTUP
# ---------------------------------------------------------------------------
async def post_init(app: Application):
    """Runs after the bot instance is initialized."""
    await db.init_db()
    logger.info("🏛️ Campus Stranger Bot initialized and ready to match students!")


def main():
    """Start the bot."""
    if not BOT_TOKEN:
        print("❌ ERROR: TELEGRAM_BOT_TOKEN environment variable is not set!")
        print("Please export TELEGRAM_BOT_TOKEN='your_token_from_botfather' in .env or your host.")
        sys.exit(1)

    # Start health server for Render / Koyeb / Heroku / Cloud Run if PORT is set
    start_health_server()

    # Build Application
    app = ApplicationBuilder().token(BOT_TOKEN).post_init(post_init).build()

    # Onboarding Conversation
    conv_handler = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(start_onboarding_callback, pattern="^start_onboarding$"),
            CommandHandler("editprofile", start_onboarding_callback)
        ],
        states={
            STATE_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, onboarding_name)],
            STATE_MAJOR: [MessageHandler(filters.TEXT & ~filters.COMMAND, onboarding_major)],
            STATE_YEAR: [MessageHandler(filters.TEXT & ~filters.COMMAND, onboarding_year)],
            STATE_DORM: [MessageHandler(filters.TEXT & ~filters.COMMAND, onboarding_dorm)],
            STATE_INTERESTS: [MessageHandler(filters.TEXT & ~filters.COMMAND, onboarding_interests)],
            STATE_HANDLE: [MessageHandler(filters.TEXT & ~filters.COMMAND, onboarding_handle)],
        },
        fallbacks=[CommandHandler("cancel", cancel_onboarding)],
    )

    app.add_handler(conv_handler)
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("find", find_command))
    app.add_handler(CommandHandler("next", next_command))
    app.add_handler(CommandHandler("stop", stop_command))
    app.add_handler(CommandHandler("reveal", reveal_command))
    app.add_handler(CommandHandler("meet", meet_command))
    app.add_handler(CommandHandler("report", report_command))
    app.add_handler(CommandHandler("profile", profile_command))
    
    # Generic Callback Query Handler
    app.add_handler(CallbackQueryHandler(callback_handler))

    # Anonymous Message Relay Handler (Text, Photos, Voice, Stickers)
    app.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, relay_message))

    # Run Bot via Long Polling (Works 24/7 on Free hosts without public SSL IP required!)
    logger.info(f" Starting {UNIVERSITY_NAME} Bot (Polling Mode)...")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
