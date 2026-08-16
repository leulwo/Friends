import re

with open("main.py", "r") as f:
    content = f.read()

replacement = """async def start_onboarding(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["onboarding"] = {}
    text = "<b>Step 1/9:</b> 👋 Welcome! What is your <b>First Name</b> or Nickname on campus?"
    
    reply_markup = ReplyKeyboardMarkup([[KeyboardButton("❌ Cancel Setup")]], resize_keyboard=True)
    
    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.message.delete()
        await context.bot.send_message(chat_id=update.effective_chat.id, text=text, parse_mode="HTML", reply_markup=reply_markup)
    else:
        await update.message.reply_text(text, parse_mode="HTML", reply_markup=reply_markup)
    return STATE_NAME"""

content = re.sub(
    r"async def start_onboarding\(update: Update, context: ContextTypes\.DEFAULT_TYPE\):.*?return STATE_NAME",
    replacement,
    content,
    flags=re.DOTALL
)

with open("main.py", "w") as f:
    f.write(content)
print("Patched start onboarding!")
