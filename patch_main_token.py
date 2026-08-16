import re

with open("main.py", "r") as f:
    content = f.read()

replacement = """def main():
    import time
    \"\"\"Start the bot.\"\"\"
    start_health_server()
    if not BOT_TOKEN or BOT_TOKEN == "mock":
        print("❌ ERROR: TELEGRAM_BOT_TOKEN environment variable is not set!")
        print("Please export TELEGRAM_BOT_TOKEN='your_token_from_botfather' in .env or your host.")
        print("Sleeping to keep the server alive so you can fix the token...")
        while True:
            time.sleep(60)

    # Build Application"""

content = re.sub(r"def main\(\):\n\s+\"\"\"Start the bot\.\"\"\"\n\s+if not BOT_TOKEN:.*?(?=# Build Application)", replacement, content, flags=re.DOTALL)

with open("main.py", "w") as f:
    f.write(content)
