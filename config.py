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
