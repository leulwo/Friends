import re

with open('main.py', 'r') as f:
    content = f.read()

start_marker = "# ---------------------------------------------------------------------------\n# ONBOARDING CONVERSATION FLOW"
end_marker = "# ---------------------------------------------------------------------------\n# CALLBACK QUERY HANDLER"

start_idx = content.find(start_marker)
end_idx = content.find(end_marker)

new_onboarding = r"""# ---------------------------------------------------------------------------
# ONBOARDING CONVERSATION FLOW (NAME -> GENDER -> MAJOR -> YEAR -> DORM -> HOBBIES -> BIO -> PHOTO)
# ---------------------------------------------------------------------------
async def start_onboarding(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["onboarding"] = {}
    text = "<b>Step 1/8:</b> What is your <b>First Name</b> or Nickname on campus?"
    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(text, parse_mode="HTML")
    else:
        await update.message.reply_text(text, parse_mode="HTML", reply_markup=ReplyKeyboardRemove())
    return STATE_NAME

async def back_to_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "<b>Step 1/8:</b> What is your <b>First Name</b> or Nickname on campus?", 
        parse_mode="HTML", 
        reply_markup=ReplyKeyboardRemove()
    )
    return STATE_NAME

async def onboarding_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["onboarding"]["name"] = update.message.text.strip()
    keyboard = [[KeyboardButton(g)] for g in GENDER_OPTIONS]
    keyboard.append([KeyboardButton("⬅️ Back")])
    await update.message.reply_text(
        "<b>Step 2/8:</b> What is your <b>Gender</b>? (Used for match filtering)",
        parse_mode="HTML",
        reply_markup=ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
    )
    return STATE_GENDER

async def back_to_gender(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[KeyboardButton(g)] for g in GENDER_OPTIONS]
    keyboard.append([KeyboardButton("⬅️ Back")])
    await update.message.reply_text(
        "<b>Step 2/8:</b> What is your <b>Gender</b>? (Used for match filtering)",
        parse_mode="HTML",
        reply_markup=ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
    )
    return STATE_GENDER

async def onboarding_gender(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["onboarding"]["gender"] = update.message.text.strip()
    await update.message.reply_text(
        "<b>Step 3/8:</b> What is your <b>Major / Department</b>? (e.g. Computer Science, Business, Biology, Medicine)",
        parse_mode="HTML",
        reply_markup=ReplyKeyboardMarkup([[KeyboardButton("⬅️ Back")]], resize_keyboard=True)
    )
    return STATE_MAJOR

async def back_to_major(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "<b>Step 3/8:</b> What is your <b>Major / Department</b>? (e.g. Computer Science, Business, Biology, Medicine)",
        parse_mode="HTML",
        reply_markup=ReplyKeyboardMarkup([[KeyboardButton("⬅️ Back")]], resize_keyboard=True)
    )
    return STATE_MAJOR

async def onboarding_major(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["onboarding"]["major"] = update.message.text.strip()
    keyboard = [[KeyboardButton(y)] for y in YEAR_OPTIONS]
    keyboard.append([KeyboardButton("⬅️ Back")])
    await update.message.reply_text(
        "<b>Step 4/8:</b> What is your <b>Academic Year</b>?",
        parse_mode="HTML",
        reply_markup=ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
    )
    return STATE_YEAR

async def back_to_year(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[KeyboardButton(y)] for y in YEAR_OPTIONS]
    keyboard.append([KeyboardButton("⬅️ Back")])
    await update.message.reply_text(
        "<b>Step 4/8:</b> What is your <b>Academic Year</b>?",
        parse_mode="HTML",
        reply_markup=ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
    )
    return STATE_YEAR

async def onboarding_year(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["onboarding"]["year"] = update.message.text.strip()
    await update.message.reply_text(
        "<b>Step 5/8:</b> What is your <b>Campus / Dorm / Area</b>? (e.g. North Dorms, Off-Campus West, Engineering Quad)",
        parse_mode="HTML",
        reply_markup=ReplyKeyboardMarkup([[KeyboardButton("⬅️ Back")]], resize_keyboard=True)
    )
    return STATE_DORM

async def back_to_dorm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "<b>Step 5/8:</b> What is your <b>Campus / Dorm / Area</b>? (e.g. North Dorms, Off-Campus West, Engineering Quad)",
        parse_mode="HTML",
        reply_markup=ReplyKeyboardMarkup([[KeyboardButton("⬅️ Back")]], resize_keyboard=True)
    )
    return STATE_DORM

async def onboarding_dorm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["onboarding"]["dorm"] = update.message.text.strip()
    await update.message.reply_text(
        "<b>Step 6/8:</b> Type 2 to 4 of your <b>Interests & Hobbies</b> separated by commas.\n\n"
        "<i>Examples: Coffee, Coding, Gaming, Gym, Anime, Music, Study Buddies</i>",
        parse_mode="HTML",
        reply_markup=ReplyKeyboardMarkup([[KeyboardButton("⬅️ Back")]], resize_keyboard=True)
    )
    return STATE_INTERESTS

async def back_to_interests(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "<b>Step 6/8:</b> Type 2 to 4 of your <b>Interests & Hobbies</b> separated by commas.\n\n"
        "<i>Examples: Coffee, Coding, Gaming, Gym, Anime, Music, Study Buddies</i>",
        parse_mode="HTML",
        reply_markup=ReplyKeyboardMarkup([[KeyboardButton("⬅️ Back")]], resize_keyboard=True)
    )
    return STATE_INTERESTS

async def onboarding_interests(update: Update, context: ContextTypes.DEFAULT_TYPE):
    raw = update.message.text.strip()
    interests = [x.strip() for x in raw.split(",") if x.strip()]
    context.user_data["onboarding"]["interests"] = interests
    await update.message.reply_text(
        f"<b>Step 7/8:</b> Write a short <b>Bio</b> about yourself.\n\n"
        f"<i>Example: 'Hey! Excited to meet people around campus. Always down for coffee!'</i>",
        parse_mode="HTML",
        reply_markup=ReplyKeyboardMarkup([[KeyboardButton("⬅️ Back")]], resize_keyboard=True)
    )
    return STATE_BIO

async def back_to_bio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f"<b>Step 7/8:</b> Write a short <b>Bio</b> about yourself.\n\n"
        f"<i>Example: 'Hey! Excited to meet people around campus. Always down for coffee!'</i>",
        parse_mode="HTML",
        reply_markup=ReplyKeyboardMarkup([[KeyboardButton("⬅️ Back")]], resize_keyboard=True)
    )
    return STATE_BIO

async def onboarding_bio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["onboarding"]["bio"] = update.message.text.strip()
    await update.message.reply_text(
        f"<b>Step 8/8:</b> Upload a <b>Real Photo</b> of yourself!\n\n"
        f"This helps build trust and makes finding matches better.\n"
        f"(Send a photo, or type /skip to use no photo):",
        parse_mode="HTML",
        reply_markup=ReplyKeyboardMarkup([[KeyboardButton("⬅️ Back")]], resize_keyboard=True)
    )
    return STATE_PHOTO

async def onboarding_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.photo:
        photo_id = update.message.photo[-1].file_id
        context.user_data["onboarding"]["photo_id"] = photo_id
    else:
        context.user_data["onboarding"]["photo_id"] = None
        if update.message.text and update.message.text.lower() != '/skip':
             await update.message.reply_text("Please send a photo, or type /skip.", reply_markup=ReplyKeyboardMarkup([[KeyboardButton("⬅️ Back")]], resize_keyboard=True))
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

"""

new_content = content[:start_idx] + new_onboarding + "\n" + content[end_idx:]

with open('main.py', 'w') as f:
    f.write(new_content)

print("Fixed!")
