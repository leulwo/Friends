import re

with open("main.py", "r") as f:
    content = f.read()

# Add STATE_AGE
content = content.replace(
    "    STATE_NAME,\n    STATE_GENDER,",
    "    STATE_NAME,\n    STATE_AGE,\n    STATE_GENDER,"
)
content = content.replace(") = range(8)", ") = range(9)")

# Update step numbers
content = content.replace("Step 1/8", "Step 1/9")
content = content.replace("Step 2/8", "Step 2/9")
content = content.replace("Step 3/8", "Step 3/9")
content = content.replace("Step 4/8", "Step 4/9")
content = content.replace("Step 5/8", "Step 5/9")
content = content.replace("Step 6/8", "Step 6/9")
content = content.replace("Step 7/8", "Step 7/9")
content = content.replace("Step 8/8", "Step 8/9")

# Add back_to_age and onboarding_age BEFORE back_to_gender
age_code = """
async def back_to_age(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "<b>Step 2/9:</b> What is your <b>Age</b>?", 
        parse_mode="HTML", 
        reply_markup=ReplyKeyboardMarkup([[KeyboardButton("⬅️ Back")]], resize_keyboard=True)
    )
    return STATE_AGE

async def onboarding_age(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["onboarding"]["age"] = update.message.text.strip()
    keyboard = [[KeyboardButton(g)] for g in GENDER_OPTIONS]
    keyboard.append([KeyboardButton("⬅️ Back")])
    await update.message.reply_text(
        "<b>Step 3/9:</b> What is your <b>Gender</b>? (Used for match filtering)",
        parse_mode="HTML",
        reply_markup=ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
    )
    return STATE_GENDER
"""

# Modify onboarding_name to go to AGE instead of GENDER
content = content.replace(
    """async def onboarding_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["onboarding"]["name"] = update.message.text.strip()
    keyboard = [[KeyboardButton(g)] for g in GENDER_OPTIONS]
    keyboard.append([KeyboardButton("⬅️ Back")])
    await update.message.reply_text(
        "<b>Step 2/9:</b> What is your <b>Gender</b>? (Used for match filtering)",
        parse_mode="HTML",
        reply_markup=ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
    )
    return STATE_GENDER""",
    """async def onboarding_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["onboarding"]["name"] = update.message.text.strip()
    await update.message.reply_text(
        "<b>Step 2/9:</b> What is your <b>Age</b>?",
        parse_mode="HTML",
        reply_markup=ReplyKeyboardMarkup([[KeyboardButton("⬅️ Back")]], resize_keyboard=True)
    )
    return STATE_AGE"""
)

# Insert new age functions
content = content.replace(
    "async def back_to_gender",
    age_code + "\nasync def back_to_gender"
)

# Modify back_to_gender to change its previous state to AGE instead of NAME
content = content.replace(
    "MessageHandler(filters.Regex(r\"^⬅️ Back$\"), back_to_name),\n                MessageHandler(filters.TEXT & ~filters.COMMAND, onboarding_gender)",
    "MessageHandler(filters.Regex(r\"^⬅️ Back$\"), back_to_age),\n                MessageHandler(filters.TEXT & ~filters.COMMAND, onboarding_gender)"
)

# Insert STATE_AGE into handler mapping
content = content.replace(
    "STATE_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, onboarding_name)],",
    "STATE_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, onboarding_name)],\n            STATE_AGE: [\n                MessageHandler(filters.Regex(r\"^⬅️ Back$\"), back_to_name),\n                MessageHandler(filters.TEXT & ~filters.COMMAND, onboarding_age)\n            ],"
)

# Profile Card - add Age
content = content.replace(
    "gender = student.get(\"gender\") or \"Not specified\"",
    "gender = student.get(\"gender\") or \"Not specified\"\n    age = student.get(\"age\") or \"Not specified\""
)
content = content.replace(
    "f\"<b>Gender:</b> {gender}\\n\"",
    "f\"<b>Gender:</b> {gender}\\n\"\n        f\"<b>Age:</b> {age}\\n\""
)

# Update Activity Hook in relay_message and start
content = content.replace(
    "async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):",
    "async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):\n    await db.update_activity(update.effective_user.id)"
)
content = content.replace(
    "async def relay_message(update: Update, context: ContextTypes.DEFAULT_TYPE):",
    "async def relay_message(update: Update, context: ContextTypes.DEFAULT_TYPE):\n    await db.update_activity(update.effective_user.id)"
)
content = content.replace(
    "async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):",
    "async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):\n    await db.update_activity(update.callback_query.from_user.id)"
)

# Update find_candidates call in search_and_display_candidate
content = content.replace(
    "candidates = await db.find_candidates(user_id, gender_filter=gender_filter, exclude_ids=exclude_ids)",
    "current_user = await db.get_user(user_id)\n    candidates = await db.find_candidates(user_id, gender_filter=gender_filter, exclude_ids=exclude_ids, current_user_profile=current_user)"
)

with open("main.py", "w") as f:
    f.write(content)

print("Main patched!")
