import os

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
DATABASE_URL = os.getenv("DATABASE_URL", "").strip()
ADMIN_USER_ID = int(os.getenv("ADMIN_USER_ID", "0"))
UNIVERSITY_NAME = os.getenv("UNIVERSITY_NAME", "Campus")

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

GENDER_OPTIONS = ["👨 Male", "👩 Female", "🌈 Non-Binary / Other", "🤐 Prefer not to say"]

FILTER_OPTIONS = [
    ("✨ Anyone (Fastest)", "filter_any"),
    ("👩 Female Students", "filter_female"),
    ("👨 Male Students", "filter_male"),
    ("🎯 Same Major / Year", "filter_major"),
]

# Telegram Sticker Pack Name (e.g. https://t.me/addstickers/FINDONEREAL)
STICKER_SET_NAME = os.getenv("STICKER_SET_NAME", "FINDONEREAL").strip()

# Optional Telegram Sticker File IDs (from Telegram animated sticker packs)
# Users can set file_ids directly or the bot auto-fetches them from STICKER_SET_NAME
# Values can be single file_id strings or lists of file_ids (e.g. for random loading animations)
STICKER_IDS = {
    "welcome": [os.getenv("STICKER_WELCOME", "")] if os.getenv("STICKER_WELCOME") else [],
    "search": [os.getenv("STICKER_SEARCH", "")] if os.getenv("STICKER_SEARCH") else [],
    "match_found": [os.getenv("STICKER_MATCH", "")] if os.getenv("STICKER_MATCH") else [],
    "chat_start": [os.getenv("STICKER_CHAT", "")] if os.getenv("STICKER_CHAT") else [],
    "loading": [os.getenv("STICKER_LOADING", "")] if os.getenv("STICKER_LOADING") else [],
    "bored_waiting": [os.getenv("STICKER_BORED", "")] if os.getenv("STICKER_BORED") else [],
    "car": [],
}


