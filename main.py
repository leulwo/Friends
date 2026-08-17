"""
=============================================================================
🏛️ CAMPUS STRANGER & FRIEND FINDER TELEGRAM BOT
Built with: python-telegram-bot v20+ (Async), Aiven.io / PostgreSQL / SQLite
=============================================================================
Features:
- Filter-based matchmaking (Gender: Female, Male, Anyone, Same Major/Hobbies)
- Rich candidate profile previews with full bio & username before chatting
- "Start Chatting" one-tap 1-on-1 direct & anonymous message bridge
- Full multimedia relay (Photos, Voice Notes, Videos, Stickers, GIFs, Docs)
- Campus meetup spot suggestions & icebreakers (/meet)
- Profile customization and edit flow (/profile, /start)
- Safety reporting & permanent block system (/report)
- Cloud health check server for 24/7 Render / Cloud hosting
=============================================================================
"""

import os
import sys
import gzip
import logging
import asyncio
import random
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import Optional, Dict, Set, List
from datetime import datetime

# Telegram Bot Imports
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardRemove,
    InputFile
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

from config import (
    BOT_TOKEN,
    DATABASE_URL,
    ADMIN_USER_ID,
    UNIVERSITY_NAME,
    CAMPUS_SPOTS,
    ICEBREAKERS,
    INTERESTS_LIST,
    YEAR_OPTIONS,
    GENDER_OPTIONS,
    FILTER_OPTIONS,
    STICKER_IDS,
    STICKER_SET_NAME
)
from database import DatabaseManager

# ---------------------------------------------------------------------------
# LOGGING CONFIGURATION
# ---------------------------------------------------------------------------
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Initialize Database Manager (Aiven / Neon / Supabase PostgreSQL or SQLite)
db = DatabaseManager(DATABASE_URL)

# ---------------------------------------------------------------------------
# CONVERSATION STATES (FOR ONBOARDING PROFILE SETUP)
# ---------------------------------------------------------------------------
(
    STATE_NAME,
    STATE_AGE,
    STATE_GENDER,
    STATE_MAJOR,
    STATE_YEAR,
    STATE_DORM,
    STATE_INTERESTS,
    STATE_BIO,
    STATE_PHOTO
) = range(9)

# ---------------------------------------------------------------------------
# IN-MEMORY ACTIVE STATE
# ---------------------------------------------------------------------------
# Active 1-on-1 matches: user_id -> partner_id
active_chats: Dict[int, int] = {}
# Waiting queue for live instant matching: user_id -> desired_filter
waiting_queue: Dict[int, str] = {}
# Seen / browsed candidates in current session: user_id -> set of candidate_ids
viewed_candidates: Dict[int, Set[int]] = {}
# Blocked pairs: user_id -> set of blocked partner_ids
blocked_pairs: Dict[int, Set[int]] = {}
# Current active candidate preview: user_id -> candidate_id
current_previews: Dict[int, int] = {}
# UI / Temporary message tracking for self-cleaning: user_id -> list of message_ids
ui_messages: Dict[int, List[int]] = {}


# ---------------------------------------------------------------------------
# SELF-CLEANING & TRANSIENT UI HELPERS (APPEAR & FADE OUT)
# ---------------------------------------------------------------------------
def track_ui_message(user_id: int, message_id: int):
    """Tracks a UI message or animation so old screens can be automatically cleaned up."""
    if user_id not in ui_messages:
        ui_messages[user_id] = []
    ui_messages[user_id].append(message_id)
    # Keep list bounded
    if len(ui_messages[user_id]) > 30:
        ui_messages[user_id] = ui_messages[user_id][-30:]


async def cleanup_user_ui(chat_id: int, context: ContextTypes.DEFAULT_TYPE, keep_last: int = 0):
    """Deletes previous transient bot UI messages and search cards to keep the chat clean."""
    if chat_id not in ui_messages or not ui_messages[chat_id]:
        return

    to_delete = ui_messages[chat_id][:-keep_last] if keep_last > 0 else ui_messages[chat_id][:]
    remaining = ui_messages[chat_id][-keep_last:] if keep_last > 0 else []
    ui_messages[chat_id] = remaining

    for msg_id in to_delete:
        try:
            await context.bot.delete_message(chat_id=chat_id, message_id=msg_id)
        except Exception:
            pass  # Message might already be deleted or expired


async def fade_out_message_after_delay(chat_id: int, message_id: int, context: ContextTypes.DEFAULT_TYPE, delay_seconds: float = 6.0):
    """Fades out (auto-deletes) an alert, animation sticker, or transient confirmation after a short duration."""
    await asyncio.sleep(delay_seconds)
    try:
        await context.bot.delete_message(chat_id=chat_id, message_id=message_id)
        if chat_id in ui_messages and message_id in ui_messages[chat_id]:
            ui_messages[chat_id].remove(message_id)
    except Exception:
        pass


def auto_fade(chat_id: int, message_id: int, context: ContextTypes.DEFAULT_TYPE, delay_seconds: float = 6.0):
    """Schedules background task to auto-delete a transient UI message or animated sticker."""
    asyncio.create_task(fade_out_message_after_delay(chat_id, message_id, context, delay_seconds))


# ---------------------------------------------------------------------------
# UI KEYBOARDS & HELPERS
# ---------------------------------------------------------------------------
def get_main_menu_keyboard() -> ReplyKeyboardMarkup:
    """Persistent action buttons in the main menu."""
    keyboard = [
        [KeyboardButton("Find Campus Match"), KeyboardButton("Gender & Filters")],
        [KeyboardButton("My Profile"), KeyboardButton("Help & Rules")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)


def get_in_chat_keyboard() -> ReplyKeyboardMarkup:
    """Action buttons while in an active 1-on-1 conversation."""
    keyboard = [
        [KeyboardButton("Next Match"), KeyboardButton("End Chat")],
        [KeyboardButton("Suggest Campus Spot"), KeyboardButton("Report User")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)


def get_filter_keyboard(current_filter: str = "filter_any") -> InlineKeyboardMarkup:
    """Filter selector keyboard."""
    buttons = []
    for label, code in FILTER_OPTIONS:
        prefix = "• " if code == current_filter else ""
        buttons.append([InlineKeyboardButton(f"{prefix}{label}", callback_data=f"apply_{code}")])
    buttons.append([
        InlineKeyboardButton("⬅️ Back to Main Menu", callback_data="back_to_main"),
        InlineKeyboardButton("👤 Back to Profile", callback_data="back_to_profile")
    ])
    return InlineKeyboardMarkup(buttons)


def format_profile_card(student: dict, is_self: bool = False) -> str:
    """Format student details into an attractive profile card."""
    name = student.get("full_name") or student.get("name") or "Campus Student"
    gender = student.get("gender") or "Not specified"
    age = student.get("age") or "Not specified"
    major = student.get("major") or "Undeclared"
    year = student.get("study_year") or student.get("year") or "Undergraduate"
    dorm = student.get("dorm") or "Campus"
    interests = student.get("interests") or "Not added yet"
    bio = student.get("bio") or "Looking to meet cool people around campus!"
    handle = student.get("social_handle")
    username = student.get("username")
    
    if not handle:
        handle = f"@{username}" if username else "Will share during chat"
    
    chats_count = student.get("total_chats", 0)

    header = "<b>YOUR STUDENT PROFILE</b>" if is_self else "<b>CAMPUS MATCH FOUND</b>"

    card = (
        f"{header}\n\n"
        f"<b>Name:</b> {name}\n"
        f"<b>Gender:</b> {gender}\n"
        f"<b>Age:</b> {age}\n"
        f"<b>Major:</b> {major} ({year})\n"
        f"<b>Campus / Area:</b> {dorm}\n"
        f"<b>Interests:</b> {interests}\n"
        f"<b>Bio:</b> <i>\"{bio}\"</i>\n"
        f"<b>Telegram:</b> <code>{handle}</code>\n"
        f"<b>Completed Chats:</b> {chats_count}\n"
    )
    return card


async def send_asset_animation(chat_id: int, animation_key: str, context: ContextTypes.DEFAULT_TYPE, auto_delete_seconds: Optional[float] = 5.0) -> bool:
    """
    Sends Telegram animated stickers (.tgs) either via configured STICKER_IDS file_id(s)
    (randomly chosen if multiple stickers match) or directly from /assets/{animation_key}.tgs.
    Optionally auto-fades / deletes the sticker after a brief animation view duration to keep chat clean.
    """
    sent_msg = None
    # 1. Check if Telegram Sticker File ID(s) are configured in STICKER_IDS
    sticker_entry = STICKER_IDS.get(animation_key)
    sticker_candidates = []
    if isinstance(sticker_entry, list):
        sticker_candidates = [s for s in sticker_entry if s]
    elif isinstance(sticker_entry, str) and sticker_entry.strip():
        sticker_candidates = [sticker_entry.strip()]

    if sticker_candidates:
        chosen_id = random.choice(sticker_candidates)
        try:
            sent_msg = await context.bot.send_sticker(chat_id=chat_id, sticker=chosen_id)
            logger.info(f"Sent sticker by file_id for {animation_key} (from {len(sticker_candidates)} options) to {chat_id}")
            if sent_msg:
                track_ui_message(chat_id, sent_msg.message_id)
                if auto_delete_seconds and auto_delete_seconds > 0:
                    auto_fade(chat_id, sent_msg.message_id, context, auto_delete_seconds)
            return True
        except Exception as e:
            logger.warning(f"Could not send sticker by file_id for {animation_key}: {e}")

    # 2. Check local assets directory for .tgs animated sticker file
    assets_dir = os.path.join(os.path.dirname(__file__), "assets")
    if not os.path.exists(assets_dir):
        return False

    # Name variations / aliases for each animation key
    aliases_map = {
        "welcome": ["welcome.tgs", "Welcome.tgs"],
        "chat_start": ["chat_start.tgs", "Chat.tgs", "chat.tgs", "Chat_start.tgs"],
        "match_found": ["match_found.tgs", "Wave Animation.tgs", "wave.tgs", "Wave.tgs", "Match_found.tgs"],
        "search": ["search.tgs", "Search.tgs", "loading.tgs", "Loader animation.tgs", "Loading Animation Bored Hand.tgs", "carr.tgs"],
        "loading": ["loading.tgs", "Loader animation.tgs", "Loader.tgs", "loader.tgs", "Loading.tgs", "Loading Animation Bored Hand.tgs", "search.tgs"],
        "bored_waiting": ["bored_waiting.tgs", "Loading Animation Bored Hand.tgs", "bored.tgs", "Bored.tgs", "loading.tgs"],
        "car": ["car.tgs", "carr.tgs", "Car.tgs"]
    }

    candidates = aliases_map.get(animation_key, [f"{animation_key}.tgs"])
    # Find all existing local matching files and pick randomly
    existing_local_candidates = [
        os.path.join(assets_dir, c) for c in candidates if os.path.exists(os.path.join(assets_dir, c))
    ]

    if existing_local_candidates:
        chosen_path = random.choice(existing_local_candidates)
        try:
            with open(chosen_path, "rb") as f:
                file_bytes = f.read()
            input_file = InputFile(file_bytes, filename=f"{animation_key}.tgs")
            sent_msg = await context.bot.send_sticker(chat_id=chat_id, sticker=input_file)
            logger.info(f"Successfully sent .tgs sticker {os.path.basename(chosen_path)} for {animation_key} to {chat_id}")
            if sent_msg:
                track_ui_message(chat_id, sent_msg.message_id)
                if auto_delete_seconds and auto_delete_seconds > 0:
                    auto_fade(chat_id, sent_msg.message_id, context, auto_delete_seconds)
            return True
        except Exception as e:
            logger.warning(f"Could not send .tgs sticker asset {chosen_path}: {e}")

    return False



# ---------------------------------------------------------------------------
# MATCHMAKING ENGINE
# ---------------------------------------------------------------------------
async def search_and_display_candidate(user_id: int, context: ContextTypes.DEFAULT_TYPE, filter_code: str = "filter_any", edit_message_id: Optional[int] = None):
    """Search for a candidate matching user's filter and display their profile with 'Start Chatting'."""
    user = await db.get_user(user_id)
    if not user:
        await context.bot.send_message(
            chat_id=user_id,
            text="⚠️ Please create your student profile first with /start or /profile!",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("📝 Create Profile", callback_data="start_onboarding")]])
        )
        return

    # Determine gender keyword for query
    gender_filter = "Any"
    if filter_code == "filter_female":
        gender_filter = "Female"
    elif filter_code == "filter_male":
        gender_filter = "Male"

    # Get list of excluded IDs (self + blocked + already viewed this session)
    seen = viewed_candidates.setdefault(user_id, set())
    user_blocks = blocked_pairs.get(user_id, set())
    exclude_ids = seen.union(user_blocks).union({user_id})

    # Fetch candidates matching filter
    current_user = await db.get_user(user_id)
    candidates = await db.find_candidates(user_id, gender_filter=gender_filter, exclude_ids=exclude_ids, current_user_profile=current_user)

    # If all candidates seen, reset session cache to allow cycling through again
    if not candidates and len(seen) > 0:
        viewed_candidates[user_id] = set()
        exclude_ids = user_blocks.union({user_id})
        current_user = await db.get_user(user_id)
    candidates = await db.find_candidates(user_id, gender_filter=gender_filter, exclude_ids=exclude_ids, current_user_profile=current_user)

    if not candidates:
        filter_label = "Female" if filter_code == "filter_female" else ("Male" if filter_code == "filter_male" else "any")
        text = (
            f"<b>No other {filter_label} students found at this exact moment.</b>\n\n"
            f"Would you like to search with broader filters or try again?"
        )
        keyboard = [
            [InlineKeyboardButton("Search Anyone (All Students)", callback_data="apply_filter_any")],
            [InlineKeyboardButton("Refresh / Try Again", callback_data=f"apply_{filter_code}")],
            [
                InlineKeyboardButton("Change Filter", callback_data="open_filter_menu"),
                InlineKeyboardButton("⬅️ Back to Main Menu", callback_data="back_to_main")
            ]
        ]
        
        if edit_message_id:
            try:
                await context.bot.edit_message_text(chat_id=user_id, message_id=edit_message_id, text=text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(keyboard))
                return
            except Exception:
                pass
        
        await cleanup_user_ui(user_id, context)
        sent = await context.bot.send_message(chat_id=user_id, text=text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(keyboard))
        track_ui_message(user_id, sent.message_id)
        return

    # Pick top candidate
    candidate = candidates[0]
    candidate_id = candidate["user_id"]
    viewed_candidates[user_id].add(candidate_id)
    current_previews[user_id] = candidate_id

    # Try sending match found animation if available (auto-fades in 4 seconds)
    await send_asset_animation(user_id, "match_found", context, auto_delete_seconds=4.0)

    # Format card
    card_text = format_profile_card(candidate, is_self=False)
    card_text += "\n<i>Tap [Start Chatting] to connect 1-on-1 now.</i>"

    # Action Buttons
    keyboard = [
        [InlineKeyboardButton("Start Chatting", callback_data=f"start_chat_{candidate_id}")],
        [
            InlineKeyboardButton("Next Candidate", callback_data=f"next_candidate_{filter_code}"),
            InlineKeyboardButton("Change Filter", callback_data="open_filter_menu")
        ],
        [InlineKeyboardButton("⬅️ Back to Main Menu", callback_data="back_to_main")]
    ]

    # Clean old preview UI to keep chat screen clean
    await cleanup_user_ui(user_id, context)
    
    photo_id = candidate.get("photo_id")
    if photo_id:
        sent = await context.bot.send_photo(chat_id=user_id, photo=photo_id, caption=card_text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(keyboard))
    else:
        sent = await context.bot.send_message(chat_id=user_id, text=card_text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(keyboard))
        
    track_ui_message(user_id, sent.message_id)


async def start_chat_session(user1_id: int, user2_id: int, context: ContextTypes.DEFAULT_TYPE):
    """Establishes a 1-on-1 active chat session between two students."""
    # Disconnect any old active sessions
    if user1_id in active_chats:
        await disconnect_chat(user1_id, context, notify_partner=False)
    if user2_id in active_chats:
        await disconnect_chat(user2_id, context, notify_partner=False)

    # Clean previous browsing/search UI cards on both sides for a pristine chat canvas
    await cleanup_user_ui(user1_id, context)
    await cleanup_user_ui(user2_id, context)

    # Link both users
    active_chats[user1_id] = user2_id
    active_chats[user2_id] = user1_id

    p1 = await db.get_user(user1_id) or {}
    p2 = await db.get_user(user2_id) or {}

    p1_name = p1.get("full_name") or "Student"
    p2_name = p2.get("full_name") or "Student"

    p1_username = p1.get("username") or p1.get("social_handle", "").replace("@", "")
    p2_username = p2.get("username") or p2.get("social_handle", "").replace("@", "")

    # Direct contact buttons
    p2_direct_link = f"https://t.me/{p2_username}" if p2_username and not p2_username.startswith("Will") else None
    p1_direct_link = f"https://t.me/{p1_username}" if p1_username and not p1_username.startswith("Will") else None

    # Trigger chat start celebration animations (auto-fades in 5s so conversation stays clear)
    await send_asset_animation(user1_id, "chat_start", context, auto_delete_seconds=5.0)
    await send_asset_animation(user2_id, "chat_start", context, auto_delete_seconds=5.0)

    # Message for User 1
    msg1 = (
        f"<b>Connected with {p2_name}</b>\n\n"
        f"You can now chat directly in this bot. All text, photos, voice notes, stickers, and files will be relayed instantly.\n"
    )
    if p2_direct_link:
        msg1 += f"<b>Direct Telegram Link:</b> <a href=\"{p2_direct_link}\">@{p2_username}</a>\n"
    msg1 += "\n<i>Use /next to skip or /stop to end the chat.</i>"

    # Message for User 2
    msg2 = (
        f"<b>{p1_name} started a 1-on-1 chat with you</b>\n\n"
        f"You can chat right here in the bot. All messages and media are delivered in real-time.\n"
    )
    if p1_direct_link:
        msg2 += f"<b>Direct Telegram Link:</b> <a href=\"{p1_direct_link}\">@{p1_username}</a>\n"
    msg2 += "\n<i>Use /next to skip or /stop to end the chat.</i>"

    try:
        sent1 = await context.bot.send_message(chat_id=user1_id, text=msg1, parse_mode="HTML", reply_markup=get_in_chat_keyboard(), disable_web_page_preview=True)
        track_ui_message(user1_id, sent1.message_id)
    except Exception as e:
        logger.error(f"Error sending chat start to {user1_id}: {e}")

    try:
        sent2 = await context.bot.send_message(chat_id=user2_id, text=msg2, parse_mode="HTML", reply_markup=get_in_chat_keyboard(), disable_web_page_preview=True)
        track_ui_message(user2_id, sent2.message_id)
    except Exception as e:
        logger.error(f"Error sending chat start to {user2_id}: {e}")

    await db.increment_chat_count(user1_id, user2_id)


async def disconnect_chat(user_id: int, context: ContextTypes.DEFAULT_TYPE, notify_partner: bool = True, reason: str = "Partner left"):
    """Disconnect active 1-on-1 session."""
    partner_id = active_chats.pop(user_id, None)
    if partner_id:
        active_chats.pop(partner_id, None)
        if notify_partner:
            try:
                await context.bot.send_message(
                    chat_id=partner_id,
                    text=f"<b>Your chat session ended.</b> ({reason})\n\nTap below to find a new match.",
                    parse_mode="HTML",
                    reply_markup=get_main_menu_keyboard()
                )
            except Exception as e:
                logger.error(f"Error notifying partner {partner_id}: {e}")


# ---------------------------------------------------------------------------
# COMMAND HANDLERS
# ---------------------------------------------------------------------------
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await db.update_activity(update.effective_user.id)
    """Handle /start command. Onboarding check."""
    user = update.effective_user
    db_user = await db.get_user(user.id)

    # Clean old transient messages
    await cleanup_user_ui(user.id, context)

    # Trigger welcome animation sticker (auto-fades in 5s)
    await send_asset_animation(user.id, "welcome", context, auto_delete_seconds=5.0)

    if not db_user:
        welcome_text = (
            f"Welcome to <b>{UNIVERSITY_NAME} Stranger & Friend Finder</b>\n\n"
            f"Connect 1-on-1 with students across campus using custom filters. "
            f"Preview profiles and start chatting instantly.\n\n"
            f"Let's set up your student profile (takes 20 seconds) 👇"
        )
        keyboard = [[InlineKeyboardButton("Create Student Profile", callback_data="start_onboarding")]]
        sent = await update.message.reply_text(
            welcome_text,
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        track_ui_message(user.id, sent.message_id)
    else:
        name = db_user.get("full_name") or "Student"
        sent = await update.message.reply_text(
            f"Welcome back, <b>{name}</b>.\n\n"
            f"What would you like to do today?",
            parse_mode="HTML",
            reply_markup=get_main_menu_keyboard()
        )
        track_ui_message(user.id, sent.message_id)


async def find_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Open match finder with filter options."""
    user_id = update.effective_user.id
    db_user = await db.get_user(user_id)

    if not db_user:
        sent = await update.message.reply_text(
            "Please complete your student profile first to find matches.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Setup Profile", callback_data="start_onboarding")]])
        )
        track_ui_message(user_id, sent.message_id)
        return

    if user_id in active_chats:
        sent = await update.message.reply_text(
            "You are currently in an active chat. Use /next to find someone else or /stop to end it.",
            reply_markup=get_in_chat_keyboard()
        )
        track_ui_message(user_id, sent.message_id)
        return

    # Check user's preferred filter
    current_filter = db_user.get("preferred_gender") or "filter_any"
    if not current_filter.startswith("filter_"):
        current_filter = "filter_any"

    text = (
        f"<b>Find Campus Match at {UNIVERSITY_NAME}</b>\n\n"
        f"Select your match filter below or search anyone:"
    )
    await cleanup_user_ui(user_id, context)
    sent = await update.message.reply_text(text, parse_mode="HTML", reply_markup=get_filter_keyboard(current_filter))
    track_ui_message(user_id, sent.message_id)


async def next_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Skip to the next student candidate."""
    user_id = update.effective_user.id
    if user_id in active_chats:
        await disconnect_chat(user_id, context, notify_partner=True, reason="Partner skipped to /next")
        sent = await update.message.reply_text("<b>Skipped.</b> Finding a new student match...", parse_mode="HTML")
        auto_fade(user_id, sent.message_id, context, delay_seconds=3.0)
        await search_and_display_candidate(user_id, context, filter_code="filter_any")
    else:
        await search_and_display_candidate(user_id, context, filter_code="filter_any")


async def stop_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """End the current chat session."""
    user_id = update.effective_user.id
    if user_id in active_chats:
        await disconnect_chat(user_id, context, notify_partner=True, reason="Partner ended the chat")
        sent = await update.message.reply_text("<b>Chat ended.</b>", parse_mode="HTML", reply_markup=get_main_menu_keyboard())
        track_ui_message(user_id, sent.message_id)
    else:
        sent = await update.message.reply_text("You are not currently in any active chat.", reply_markup=get_main_menu_keyboard())
        auto_fade(user_id, sent.message_id, context, delay_seconds=4.0)


async def meet_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Suggest random campus meetup spot and icebreaker."""
    user_id = update.effective_user.id
    if user_id not in active_chats:
        sent = await update.message.reply_text("Connect with a student first using /find.")
        auto_fade(user_id, sent.message_id, context, delay_seconds=4.0)
        return

    partner_id = active_chats[user_id]
    spot = random.choice(CAMPUS_SPOTS)
    icebreaker = random.choice(ICEBREAKERS)

    text = (
        f"<b>Campus Meetup Suggestion</b>\n\n"
        f"<b>Spot:</b> {spot}\n"
        f"<b>Icebreaker Question:</b> <i>\"{icebreaker}\"</i>\n\n"
        f"<i>Want to meet there or grab coffee together? Send a message to your partner.</i>"
    )

    await update.message.reply_text(text, parse_mode="HTML")
    await context.bot.send_message(chat_id=partner_id, text=text, parse_mode="HTML")


async def report_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Report and permanently block inappropriate partner."""
    user_id = update.effective_user.id
    if user_id not in active_chats:
        sent = await update.message.reply_text("You can only report a user during an active chat.")
        auto_fade(user_id, sent.message_id, context, delay_seconds=4.0)
        return

    partner_id = active_chats[user_id]
    blocked_pairs.setdefault(user_id, set()).add(partner_id)
    blocked_pairs.setdefault(partner_id, set()).add(user_id)

    await disconnect_chat(user_id, context, notify_partner=True, reason="Reported and blocked")
    await db.log_report(user_id, partner_id, "Inappropriate chat behavior report")

    sent = await update.message.reply_text(
        "<b>User reported and permanently blocked.</b> You will not be matched with them again.\n\nSearching for a new student...",
        parse_mode="HTML"
    )
    auto_fade(user_id, sent.message_id, context, delay_seconds=4.0)
    await search_and_display_candidate(user_id, context, filter_code="filter_any")


async def profile_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show current user's profile with edit button."""
    user_id = update.effective_user.id
    p = await db.get_user(user_id)
    if not p:
        sent = await update.message.reply_text(
            "No profile found. Let's create one.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Create Profile", callback_data="start_onboarding")]])
        )
        track_ui_message(user_id, sent.message_id)
        return

    await cleanup_user_ui(user_id, context)
    card = format_profile_card(p, is_self=True)
    keyboard = [
        [InlineKeyboardButton("✏️ Edit Profile", callback_data="start_onboarding")],
        [InlineKeyboardButton("🎯 Change Match Filters", callback_data="open_filter_menu")],
        [InlineKeyboardButton("⬅️ Back to Main Menu", callback_data="back_to_main")]
    ]
    photo_id = p.get("photo_id")
    if photo_id:
        sent = await update.message.reply_photo(photo=photo_id, caption=card, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(keyboard))
    else:
        sent = await update.message.reply_text(card, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(keyboard))
    track_ui_message(user_id, sent.message_id)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show rules and help with back button to main menu."""
    user_id = update.effective_user.id
    await cleanup_user_ui(user_id, context)
    keyboard = [[InlineKeyboardButton("⬅️ Back to Main Menu", callback_data="back_to_main")]]
    sent = await update.message.reply_text(
        f"<b>{UNIVERSITY_NAME} Bot Rules & Help</b>\n\n"
        "1. <b>Respect:</b> Treat fellow students with kindness and respect.\n"
        "2. <b>Filter Match:</b> Choose your filters (Female, Male, Anyone) before searching.\n"
        "3. <b>Profile Preview:</b> Review student bios and handles before tapping [Start Chatting].\n"
        "4. <b>Safety:</b> Always meet in public campus areas (Student Union, Library, Quad).\n"
        "5. <b>Block:</b> Use /report to permanently block inappropriate users.\n\n"
        "<b>Commands:</b>\n"
        "/find - Find matches with filters\n"
        "/next - Next student\n"
        "/stop - End chat\n"
        "/meet - Campus spot & icebreakers\n"
        "/profile - View and edit your profile\n"
        "/report - Block & report partner\n"
        "/help - Rules & guidelines",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    track_ui_message(user_id, sent.message_id)


# ---------------------------------------------------------------------------
# MESSAGE RELAY (1-ON-1 CHAT BRIDGE & MEDIA SUPPORT)
# ---------------------------------------------------------------------------
async def relay_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await db.update_activity(update.effective_user.id)
    """Relays text, images, videos, voice notes, stickers, and documents between matched pairs."""
    user_id = update.effective_user.id
    text = update.message.text if update.message else ""

    # Menu triggers
    if text in ["Find Campus Match", "🔍 Find Campus Match"]:
        await find_command(update, context)
        return
    elif text in ["Gender & Filters", "🎯 Gender & Filters"]:
        await find_command(update, context)
        return
    elif text in ["Next Match", "⏭️ Next Match"]:
        await next_command(update, context)
        return
    elif text in ["End Chat", "🛑 End Chat"]:
        await stop_command(update, context)
        return
    elif text in ["Suggest Campus Spot", "📍 Suggest Campus Spot"]:
        await meet_command(update, context)
        return
    elif text in ["Report User", "🛡️ Report User"]:
        await report_command(update, context)
        return
    elif text in ["My Profile", "👤 My Student Profile"]:
        await profile_command(update, context)
        return
    elif text in ["Help & Rules", "❓ Help & Rules"]:
        await help_command(update, context)
        return

    # Check if user is in an active chat
    if user_id not in active_chats:
        await update.message.reply_text(
            "You are not in an active chat right now. Tap <b>Find Campus Match</b> below to connect with students.",
            parse_mode="HTML",
            reply_markup=get_main_menu_keyboard()
        )
        return

    partner_id = active_chats[user_id]

    # Forward message & media types
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
            await update.message.reply_text("ℹ️ This media format is not supported.")
    except Exception as e:
        logger.error(f"Error relaying message from {user_id} to {partner_id}: {e}")
        await update.message.reply_text("⚠️ Could not deliver message. Your partner might have disconnected.")
        await disconnect_chat(user_id, context, notify_partner=False)


# ---------------------------------------------------------------------------
# ONBOARDING CONVERSATION FLOW (NAME -> AGE -> GENDER -> MAJOR -> YEAR -> DORM -> HOBBIES -> BIO -> PHOTO)
# ---------------------------------------------------------------------------
async def start_onboarding(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["onboarding"] = {}
    text = "<b>Step 1/9:</b> 👋 Welcome! What is your <b>First Name</b> or Nickname on campus?"
    
    reply_markup = ReplyKeyboardMarkup([[KeyboardButton("⬅️ Back to Main Menu"), KeyboardButton("❌ Cancel Setup")]], resize_keyboard=True)
    
    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.message.delete()
        await context.bot.send_message(chat_id=update.effective_chat.id, text=text, parse_mode="HTML", reply_markup=reply_markup)
    else:
        await update.message.reply_text(text, parse_mode="HTML", reply_markup=reply_markup)
    return STATE_NAME

async def back_to_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "<b>Step 1/9:</b> 👋 Welcome! What is your <b>First Name</b> or Nickname on campus?", 
        parse_mode="HTML", 
        reply_markup=ReplyKeyboardMarkup([[KeyboardButton("⬅️ Back to Main Menu"), KeyboardButton("❌ Cancel Setup")]], resize_keyboard=True)
    )
    return STATE_NAME

async def onboarding_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["onboarding"]["name"] = update.message.text.strip()
    await update.message.reply_text(
        "<b>Step 2/9:</b> What is your <b>Age</b>?",
        parse_mode="HTML",
        reply_markup=ReplyKeyboardMarkup([[KeyboardButton("⬅️ Back"), KeyboardButton("❌ Cancel Setup")]], resize_keyboard=True)
    )
    return STATE_AGE


async def back_to_age(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "<b>Step 2/9:</b> What is your <b>Age</b>?", 
        parse_mode="HTML", 
        reply_markup=ReplyKeyboardMarkup([[KeyboardButton("⬅️ Back"), KeyboardButton("❌ Cancel Setup")]], resize_keyboard=True)
    )
    return STATE_AGE

async def onboarding_age(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["onboarding"]["age"] = update.message.text.strip()
    keyboard = [[KeyboardButton(g)] for g in GENDER_OPTIONS]
    keyboard.append([KeyboardButton("⬅️ Back"), KeyboardButton("❌ Cancel Setup")])
    await update.message.reply_text(
        "<b>Step 3/9:</b> What is your <b>Gender</b>? (Used for match filtering)",
        parse_mode="HTML",
        reply_markup=ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
    )
    return STATE_GENDER

async def back_to_gender(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[KeyboardButton(g)] for g in GENDER_OPTIONS]
    keyboard.append([KeyboardButton("⬅️ Back"), KeyboardButton("❌ Cancel Setup")])
    await update.message.reply_text(
        "<b>Step 3/9:</b> What is your <b>Gender</b>? (Used for match filtering)",
        parse_mode="HTML",
        reply_markup=ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
    )
    return STATE_GENDER

async def onboarding_gender(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["onboarding"]["gender"] = update.message.text.strip()
    await update.message.reply_text(
        "<b>Step 4/9:</b> What is your <b>Major / Department</b>? (e.g. Computer Science, Business, Biology, Medicine)",
        parse_mode="HTML",
        reply_markup=ReplyKeyboardMarkup([[KeyboardButton("⬅️ Back"), KeyboardButton("❌ Cancel Setup")]], resize_keyboard=True)
    )
    return STATE_MAJOR

async def back_to_major(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "<b>Step 4/9:</b> What is your <b>Major / Department</b>? (e.g. Computer Science, Business, Biology, Medicine)",
        parse_mode="HTML",
        reply_markup=ReplyKeyboardMarkup([[KeyboardButton("⬅️ Back"), KeyboardButton("❌ Cancel Setup")]], resize_keyboard=True)
    )
    return STATE_MAJOR

async def onboarding_major(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["onboarding"]["major"] = update.message.text.strip()
    keyboard = [[KeyboardButton(y)] for y in YEAR_OPTIONS]
    keyboard.append([KeyboardButton("⬅️ Back"), KeyboardButton("❌ Cancel Setup")])
    await update.message.reply_text(
        "<b>Step 5/9:</b> What is your <b>Academic Year</b>?",
        parse_mode="HTML",
        reply_markup=ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
    )
    return STATE_YEAR

async def back_to_year(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[KeyboardButton(y)] for y in YEAR_OPTIONS]
    keyboard.append([KeyboardButton("⬅️ Back"), KeyboardButton("❌ Cancel Setup")])
    await update.message.reply_text(
        "<b>Step 5/9:</b> What is your <b>Academic Year</b>?",
        parse_mode="HTML",
        reply_markup=ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
    )
    return STATE_YEAR

async def onboarding_year(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["onboarding"]["year"] = update.message.text.strip()
    await update.message.reply_text(
        "<b>Step 6/9:</b> What is your <b>Campus / Dorm / Area</b>? (e.g. North Dorms, Off-Campus West, Engineering Quad)",
        parse_mode="HTML",
        reply_markup=ReplyKeyboardMarkup([[KeyboardButton("⬅️ Back"), KeyboardButton("❌ Cancel Setup")]], resize_keyboard=True)
    )
    return STATE_DORM

async def back_to_dorm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "<b>Step 6/9:</b> What is your <b>Campus / Dorm / Area</b>? (e.g. North Dorms, Off-Campus West, Engineering Quad)",
        parse_mode="HTML",
        reply_markup=ReplyKeyboardMarkup([[KeyboardButton("⬅️ Back"), KeyboardButton("❌ Cancel Setup")]], resize_keyboard=True)
    )
    return STATE_DORM

async def onboarding_dorm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["onboarding"]["dorm"] = update.message.text.strip()
    await update.message.reply_text(
        "<b>Step 7/9:</b> Type 2 to 4 of your <b>Interests & Hobbies</b> separated by commas.\n\n"
        "<i>Examples: Coffee, Coding, Gaming, Gym, Anime, Music, Study Buddies</i>",
        parse_mode="HTML",
        reply_markup=ReplyKeyboardMarkup([[KeyboardButton("⬅️ Back"), KeyboardButton("❌ Cancel Setup")]], resize_keyboard=True)
    )
    return STATE_INTERESTS

async def back_to_interests(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "<b>Step 7/9:</b> Type 2 to 4 of your <b>Interests & Hobbies</b> separated by commas.\n\n"
        "<i>Examples: Coffee, Coding, Gaming, Gym, Anime, Music, Study Buddies</i>",
        parse_mode="HTML",
        reply_markup=ReplyKeyboardMarkup([[KeyboardButton("⬅️ Back"), KeyboardButton("❌ Cancel Setup")]], resize_keyboard=True)
    )
    return STATE_INTERESTS

async def onboarding_interests(update: Update, context: ContextTypes.DEFAULT_TYPE):
    raw = update.message.text.strip()
    interests = [x.strip() for x in raw.split(",") if x.strip()]
    context.user_data["onboarding"]["interests"] = interests
    await update.message.reply_text(
        f"<b>Step 8/9:</b> Write a short <b>Bio</b> about yourself.\n\n"
        f"<i>Example: 'Hey! Excited to meet people around campus. Always down for coffee!'</i>",
        parse_mode="HTML",
        reply_markup=ReplyKeyboardMarkup([[KeyboardButton("⬅️ Back"), KeyboardButton("❌ Cancel Setup")]], resize_keyboard=True)
    )
    return STATE_BIO

async def back_to_bio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f"<b>Step 8/9:</b> Write a short <b>Bio</b> about yourself.\n\n"
        f"<i>Example: 'Hey! Excited to meet people around campus. Always down for coffee!'</i>",
        parse_mode="HTML",
        reply_markup=ReplyKeyboardMarkup([[KeyboardButton("⬅️ Back"), KeyboardButton("❌ Cancel Setup")]], resize_keyboard=True)
    )
    return STATE_BIO

async def onboarding_bio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["onboarding"]["bio"] = update.message.text.strip()
    await update.message.reply_text(
        f"<b>Step 9/9:</b> Upload a <b>Real Photo</b> of yourself!\n\n"
        f"This helps build trust and makes finding matches better.\n"
        f"(Send a photo, or type /skip to use no photo):",
        parse_mode="HTML",
        reply_markup=ReplyKeyboardMarkup([[KeyboardButton("⬅️ Back"), KeyboardButton("❌ Cancel Setup")]], resize_keyboard=True)
    )
    return STATE_PHOTO

async def onboarding_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.photo:
        photo_id = update.message.photo[-1].file_id
        context.user_data["onboarding"]["photo_id"] = photo_id
    else:
        context.user_data["onboarding"]["photo_id"] = None
        if update.message.text and update.message.text.lower() != '/skip':
             await update.message.reply_text("Please send a photo, or type /skip.", reply_markup=ReplyKeyboardMarkup([[KeyboardButton("⬅️ Back"), KeyboardButton("❌ Cancel Setup")]], resize_keyboard=True))
             return STATE_PHOTO
             
    user = update.effective_user
    data = context.user_data["onboarding"]
    data["user_id"] = user.id
    data["username"] = user.username or ""
    data["preferred_gender"] = "filter_any"

    await db.save_user(data)

    await send_asset_animation(user.id, "welcome", context)

    await update.message.reply_text(
        f"<b>Profile Created Successfully</b>\n\n"
        f"You are all set to find new friends across {UNIVERSITY_NAME}.\n"
        f"Tap <b>Find Campus Match</b> below to choose filters and start matching.",
        parse_mode="HTML",
        reply_markup=get_main_menu_keyboard()
    )
    return ConversationHandler.END

async def cancel_onboarding(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Profile setup cancelled.", reply_markup=get_main_menu_keyboard())
    return ConversationHandler.END


# ---------------------------------------------------------------------------
# CALLBACK QUERY HANDLER (FILTERS, CANDIDATE CYCLING, START CHATTING)
# ---------------------------------------------------------------------------
async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await db.update_activity(update.callback_query.from_user.id)
    query = update.callback_query
    await query.answer()
    data = query.data
    user_id = query.from_user.id
    msg_id = query.message.message_id if query.message else None

    # 0. Back to Main Menu
    if data == "back_to_main":
        user = await db.get_user(user_id)
        name = user.get("full_name") if user else "Student"
        text = f"<b>Main Menu</b>\n\nWelcome back, <b>{name}</b>! What would you like to do?"
        keyboard = [
            [InlineKeyboardButton("🔍 Find Campus Match", callback_data="apply_filter_any")],
            [InlineKeyboardButton("🎯 Gender & Filters", callback_data="open_filter_menu")],
            [InlineKeyboardButton("👤 My Student Profile", callback_data="back_to_profile")]
        ]
        if query.message:
            try:
                if query.message.photo:
                    await query.message.delete()
                    sent = await context.bot.send_message(
                        chat_id=user_id,
                        text=text,
                        parse_mode="HTML",
                        reply_markup=get_main_menu_keyboard()
                    )
                    track_ui_message(user_id, sent.message_id)
                else:
                    await query.edit_message_text(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(keyboard))
            except Exception:
                sent = await context.bot.send_message(
                    chat_id=user_id,
                    text=text,
                    parse_mode="HTML",
                    reply_markup=get_main_menu_keyboard()
                )
                track_ui_message(user_id, sent.message_id)
        return

    # 1. Open Filter Menu
    elif data == "open_filter_menu":
        user = await db.get_user(user_id) or {}
        current_pref = user.get("preferred_gender", "filter_any")
        text = (
            f"🎯 <b>Match Filter Settings</b>\n\n"
            f"Select who you want to search for across {UNIVERSITY_NAME}:"
        )
        if query.message and query.message.photo:
            await query.message.delete()
            sent = await context.bot.send_message(chat_id=user_id, text=text, parse_mode="HTML", reply_markup=get_filter_keyboard(current_pref))
            track_ui_message(user_id, sent.message_id)
        else:
            await query.edit_message_text(text, parse_mode="HTML", reply_markup=get_filter_keyboard(current_pref))
        return

    elif data == "back_to_profile":
        user = await db.get_user(user_id)
        if not user:
            await query.edit_message_text("No profile found.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Create Profile", callback_data="start_onboarding")]]))
            return
        card = format_profile_card(user, is_self=True)
        keyboard = [
            [InlineKeyboardButton("✏️ Edit Profile", callback_data="start_onboarding")],
            [InlineKeyboardButton("🎯 Change Match Filters", callback_data="open_filter_menu")],
            [InlineKeyboardButton("⬅️ Back to Main Menu", callback_data="back_to_main")]
        ]
        if query.message and query.message.photo:
            await query.edit_message_caption(caption=card, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(keyboard))
        else:
            await query.edit_message_text(card, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(keyboard))
        return

    # 2. Apply a Filter and Search
    elif data.startswith("apply_"):
        filter_code = data.replace("apply_", "")
        await db.update_preference(user_id, filter_code)
        await send_asset_animation(user_id, "search", context)
        await search_and_display_candidate(user_id, context, filter_code=filter_code, edit_message_id=None)
        return

    # 3. Next Candidate
    elif data.startswith("next_candidate_"):
        filter_code = data.replace("next_candidate_", "")
        await send_asset_animation(user_id, "search", context)
        await search_and_display_candidate(user_id, context, filter_code=filter_code, edit_message_id=None)
        return

    # 4. START CHATTING BUTTON CLICKED!
    elif data.startswith("start_chat_"):
        target_candidate_id = int(data.replace("start_chat_", ""))
        
        # Check if already chatting with someone
        if user_id in active_chats:
            await query.edit_message_text("⚠️ You are already in an active chat. Use /stop to end it first.")
            return

        # Start 1-on-1 session
        await query.edit_message_text("🚀 <b>Connecting to 1-on-1 chat...</b>", parse_mode="HTML")
        await start_chat_session(user_id, target_candidate_id, context)
        return


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

    # Automatically load stickers from Telegram Sticker Pack (e.g. FINDONEREAL)
    if STICKER_SET_NAME:
        try:
            sticker_set = await app.bot.get_sticker_set(name=STICKER_SET_NAME)
            logger.info(f"🎨 Found Telegram Sticker Pack '{STICKER_SET_NAME}' with {len(sticker_set.stickers)} stickers")
            
            # User's exact clock emoji & number mapping:
            # 1 o'clock (🕐, 1) -> loading
            # 2 o'clock (🕑, 2) -> match_found (Wave Animation)
            # 3 o'clock (🕒, 3) -> car (carr.tgs)
            # 4 o'clock (🕓, 4) -> bored_waiting (Loading Animation Bored Hand)
            # 5 o'clock (🕔, 5) -> loading (loader animation)
            # 6 o'clock (🕕, 6) -> search (search.tgs)
            # 7 o'clock (🕖, 7) -> chat_start (Chat.tgs)
            # 8 o'clock (🕗, 8) -> welcome (Welcome.tgs)
            # Helper to append sticker to list without duplicates
            def add_sticker(action: str, file_id: str):
                if action not in STICKER_IDS or not isinstance(STICKER_IDS[action], list):
                    STICKER_IDS[action] = []
                if file_id not in STICKER_IDS[action]:
                    STICKER_IDS[action].append(file_id)

            for idx, sticker in enumerate(sticker_set.stickers):
                emoji = sticker.emoji or ""
                logger.info(f"Sticker [{idx}]: emoji='{emoji}', file_id='{sticker.file_id[:16]}...'")

                # Match 1 o'clock (🕐, 1) -> loading/search animation pool
                if "🕐" in emoji or "1️⃣" in emoji or emoji == "1" or idx == 0:
                    add_sticker("loading", sticker.file_id)
                    add_sticker("search", sticker.file_id)
                # Match 2 o'clock (🕑, 2) -> match_found (Wave Animation) / chat_start
                if "🕑" in emoji or "2️⃣" in emoji or emoji == "2" or idx == 1:
                    add_sticker("match_found", sticker.file_id)
                # Match 3 o'clock (🕒, 3) -> car (carr.tgs) / search / loading pool
                if "🕒" in emoji or "3️⃣" in emoji or emoji == "3" or idx == 2:
                    add_sticker("car", sticker.file_id)
                    add_sticker("search", sticker.file_id)
                    add_sticker("loading", sticker.file_id)
                # Match 4 o'clock (🕓, 4) -> bored_waiting (Loading Animation Bored Hand) / loading pool
                if "🕓" in emoji or "4️⃣" in emoji or emoji == "4" or idx == 3:
                    add_sticker("bored_waiting", sticker.file_id)
                    add_sticker("loading", sticker.file_id)
                # Match 5 o'clock (🕔, 5) -> loading (loader animation) / search pool
                if "🕔" in emoji or "5️⃣" in emoji or emoji == "5" or idx == 4:
                    add_sticker("loading", sticker.file_id)
                    add_sticker("search", sticker.file_id)
                # Match 6 o'clock (🕕, 6) -> search (search.tgs) / loading pool
                if "🕕" in emoji or "6️⃣" in emoji or emoji == "6" or idx == 5:
                    add_sticker("search", sticker.file_id)
                    add_sticker("loading", sticker.file_id)
                # Match 7 o'clock (🕖, 7) -> chat_start (Chat.tgs)
                if "🕖" in emoji or "7️⃣" in emoji or emoji == "7" or idx == 6:
                    add_sticker("chat_start", sticker.file_id)
                # Match 8 o'clock (🕗, 8) -> welcome (Welcome.tgs)
                if "🕗" in emoji or "8️⃣" in emoji or emoji == "8" or idx == 7:
                    add_sticker("welcome", sticker.file_id)

            logger.info(f"Loaded STICKER_IDS mapping: {list(STICKER_IDS.keys())}")
        except Exception as e:
            logger.warning(f"Could not auto-fetch sticker set '{STICKER_SET_NAME}': {e}")

    logger.info("🏛️ Campus Stranger Bot initialized and ready to match students!")


def main():
    import time
    """Start the bot."""
    start_health_server()
    if not BOT_TOKEN or BOT_TOKEN == "mock":
        print("❌ ERROR: TELEGRAM_BOT_TOKEN environment variable is not set!")
        print("Please export TELEGRAM_BOT_TOKEN='your_token_from_botfather' in .env or your host.")
        print("Sleeping to keep the server alive so you can fix the token...")
        while True:
            time.sleep(60)

    # Build Application# Build Application
    app = ApplicationBuilder().token(BOT_TOKEN).post_init(post_init).build()

    # Onboarding Conversation
    conv_handler = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(start_onboarding, pattern="^start_onboarding$"),
            CommandHandler("editprofile", start_onboarding)
        ],
        states={
            STATE_NAME: [
                MessageHandler(filters.Regex(r"^(⬅️ Back|⬅️ Back to Main Menu|❌ Cancel Setup|Cancel|/cancel)$"), cancel_onboarding),
                MessageHandler(filters.TEXT & ~filters.COMMAND, onboarding_name)
            ],
            STATE_AGE: [
                MessageHandler(filters.Regex(r"^(⬅️ Back|Back)$"), back_to_name),
                MessageHandler(filters.Regex(r"^(❌ Cancel Setup|Cancel|/cancel)$"), cancel_onboarding),
                MessageHandler(filters.TEXT & ~filters.COMMAND, onboarding_age)
            ],
            STATE_GENDER: [
                MessageHandler(filters.Regex(r"^(⬅️ Back|Back)$"), back_to_age),
                MessageHandler(filters.Regex(r"^(❌ Cancel Setup|Cancel|/cancel)$"), cancel_onboarding),
                MessageHandler(filters.TEXT & ~filters.COMMAND, onboarding_gender)
            ],
            STATE_MAJOR: [
                MessageHandler(filters.Regex(r"^(⬅️ Back|Back)$"), back_to_gender),
                MessageHandler(filters.Regex(r"^(❌ Cancel Setup|Cancel|/cancel)$"), cancel_onboarding),
                MessageHandler(filters.TEXT & ~filters.COMMAND, onboarding_major)
            ],
            STATE_YEAR: [
                MessageHandler(filters.Regex(r"^(⬅️ Back|Back)$"), back_to_major),
                MessageHandler(filters.Regex(r"^(❌ Cancel Setup|Cancel|/cancel)$"), cancel_onboarding),
                MessageHandler(filters.TEXT & ~filters.COMMAND, onboarding_year)
            ],
            STATE_DORM: [
                MessageHandler(filters.Regex(r"^(⬅️ Back|Back)$"), back_to_year),
                MessageHandler(filters.Regex(r"^(❌ Cancel Setup|Cancel|/cancel)$"), cancel_onboarding),
                MessageHandler(filters.TEXT & ~filters.COMMAND, onboarding_dorm)
            ],
            STATE_INTERESTS: [
                MessageHandler(filters.Regex(r"^(⬅️ Back|Back)$"), back_to_dorm),
                MessageHandler(filters.Regex(r"^(❌ Cancel Setup|Cancel|/cancel)$"), cancel_onboarding),
                MessageHandler(filters.TEXT & ~filters.COMMAND, onboarding_interests)
            ],
            STATE_BIO: [
                MessageHandler(filters.Regex(r"^(⬅️ Back|Back)$"), back_to_interests),
                MessageHandler(filters.Regex(r"^(❌ Cancel Setup|Cancel|/cancel)$"), cancel_onboarding),
                MessageHandler(filters.TEXT & ~filters.COMMAND, onboarding_bio)
            ],
            STATE_PHOTO: [
                MessageHandler(filters.Regex(r"^(⬅️ Back|Back)$"), back_to_bio),
                MessageHandler(filters.Regex(r"^(❌ Cancel Setup|Cancel|/cancel)$"), cancel_onboarding),
                MessageHandler((filters.PHOTO | filters.TEXT) & ~filters.COMMAND, onboarding_photo)
            ],
        },
        fallbacks=[
            CommandHandler("cancel", cancel_onboarding),
            MessageHandler(filters.Regex(r"^(❌ Cancel Setup|Cancel)$"), cancel_onboarding)
        ],
    )

    app.add_handler(conv_handler)
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("find", find_command))
    app.add_handler(CommandHandler("filter", find_command))
    app.add_handler(CommandHandler("filters", find_command))
    app.add_handler(CommandHandler("next", next_command))
    app.add_handler(CommandHandler("stop", stop_command))
    app.add_handler(CommandHandler("meet", meet_command))
    app.add_handler(CommandHandler("report", report_command))
    app.add_handler(CommandHandler("profile", profile_command))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("rules", help_command))
    
    # Generic Callback Query Handler (Filters, Start Chatting, Next candidate)
    app.add_handler(CallbackQueryHandler(callback_handler))

    # Anonymous & Direct Message Relay Handler (Text, Photos, Voice, Videos, Stickers, Docs)
    app.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, relay_message))

    # Run Bot via Long Polling
    logger.info(f"🚀 Starting {UNIVERSITY_NAME} Bot (Polling Mode)...")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
