import re

with open("main.py", "r") as f:
    content = f.read()

# 1. Update get_filter_keyboard to include a Back button
content = content.replace(
    "        buttons.append([InlineKeyboardButton(f\"{prefix}{label}\", callback_data=f\"apply_{code}\")])\n    return InlineKeyboardMarkup(buttons)",
    "        buttons.append([InlineKeyboardButton(f\"{prefix}{label}\", callback_data=f\"apply_{code}\")])\n    buttons.append([InlineKeyboardButton(\"⬅️ Back to Profile\", callback_data=\"back_to_profile\")])\n    return InlineKeyboardMarkup(buttons)"
)

# 2. Add handler for "back_to_profile" in callback_handler
back_to_profile_handler = """    elif data == "back_to_profile":
        user = await db.get_user(user_id)
        if not user:
            await query.edit_message_text("No profile found.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Create Profile", callback_data="start_onboarding")]]))
            return
        card = format_profile_card(user, is_self=True)
        keyboard = [
            [InlineKeyboardButton("Edit Profile", callback_data="start_onboarding")],
            [InlineKeyboardButton("Change Match Filters", callback_data="open_filter_menu")]
        ]
        await query.edit_message_text(card, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(keyboard))
        return

    # 2. Apply a Filter and Search"""

content = content.replace(
    "    # 2. Apply a Filter and Search",
    back_to_profile_handler
)

# 3. Fix start_onboarding and back_to_name so Step 1 has a "Cancel" button
content = content.replace(
    "await update.message.reply_text(text, parse_mode=\"HTML\", reply_markup=ReplyKeyboardRemove())",
    "await update.message.reply_text(text, parse_mode=\"HTML\", reply_markup=ReplyKeyboardMarkup([[KeyboardButton(\"❌ Cancel Setup\")]], resize_keyboard=True))"
)

content = content.replace(
    "reply_markup=ReplyKeyboardRemove()",
    "reply_markup=ReplyKeyboardMarkup([[KeyboardButton(\"❌ Cancel Setup\")]], resize_keyboard=True)"
)

# 4. Add "❌ Cancel Setup" to the onboarding fallbacks
content = content.replace(
    "fallbacks=[CommandHandler(\"cancel\", cancel_onboarding), MessageHandler(filters.Regex(r\"^⬅️ Back$\"), cancel_onboarding)]",
    "fallbacks=[CommandHandler(\"cancel\", cancel_onboarding), MessageHandler(filters.Regex(r\"^⬅️ Back$\"), cancel_onboarding), MessageHandler(filters.Regex(r\"^❌ Cancel Setup$\"), cancel_onboarding)]"
)

# Write back
with open("main.py", "w") as f:
    f.write(content)
print("Patched back buttons!")
