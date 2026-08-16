# 🏛️ Campus Stranger & Friend Finder Telegram Bot

An Omegle-style anonymous 1-on-1 chatting bot for university & college students, built with `python-telegram-bot` v20+ (async) and PostgreSQL / SQLite.

---

## 🚀 How to Deploy on Render (Step-by-Step)

You can host this bot for **FREE 24/7** on [Render.com](https://render.com).

### Method 1: Deploy with Git / GitHub (Recommended)

1. **Push your code to GitHub**:
   - Create a new GitHub repository (public or private).
   - Push all files from this folder (`main.py`, `database.py`, `config.py`, `requirements.txt`, `Procfile`, `render.yaml`).

2. **Open Render**:
   - Go to [dashboard.render.com](https://dashboard.render.com) and sign in.
   - Click **New +** → **Web Service** (or **Background Worker**).

3. **Connect Your Repository**:
   - Select your GitHub repo.
   - Set the settings:
     - **Runtime:** `Python 3`
     - **Build Command:** `pip install -r requirements.txt`
     - **Start Command:** `python main.py`
     - **Instance Type:** `Free`

4. **Add Environment Variables**:
   Under **Environment Variables**, add:
   - `TELEGRAM_BOT_TOKEN`: `123456789:ABCdef...` *(obtained from @BotFather on Telegram)*
   - `UNIVERSITY_NAME`: `Your College / University Name` *(e.g. Stanford, Oxford, UCLA)*
   - `DATABASE_URL`: `postgres://avnadmin:your_password@pg-service-name.aivencloud.com:12345/defaultdb?sslmode=require` *(Your Aiven.io PostgreSQL Service URI. If left blank, it automatically uses local SQLite)*

5. **Click "Create Web Service"**:
   - Render will build the dependencies and start `main.py`.
   - Your bot is now **Live 24/7** on Telegram!

---

## 🗄️ Setting Up Aiven.io PostgreSQL Database

1. Go to [aiven.io](https://aiven.io) and create a free account.
2. Click **Create Service** → select **PostgreSQL**.
3. Choose your cloud provider and region (free tier available).
4. Once created, copy the **Service URI** from the Overview tab (it looks like `postgres://avnadmin:xxx@pg-xxx.aivencloud.com:port/defaultdb?sslmode=require`).
5. Paste it as your `DATABASE_URL` environment variable in Render or your `.env` file.
6. The bot will automatically create the tables (`students`, `chat_logs`, `reports`) on startup!

---

## 🖼️ Media & Image Sharing Support

During active anonymous 1-on-1 chats, students can exchange:
- 📸 **Photos & Images** (with captions)
- 🎬 **GIFs & Animations**
- 🎥 **Videos** & ⭕ **Round Video Notes**
- 🎙️ **Voice Notes** & 🎵 **Audio Files**
- 📄 **Documents & PDFs** (study materials, slides)
- 🎭 **Stickers & Animated Stickers**

All media is relayed anonymously through the bot without exposing the sender's Telegram identity or phone number.

---

## 💻 How to Run Locally

```bash
# 1. Clone or download files
# 2. Install dependencies
pip install -r requirements.txt

# 3. Create .env file or set environment variables:
export TELEGRAM_BOT_TOKEN="your_botfather_token_here"
export UNIVERSITY_NAME="My Campus"

# 4. Start the bot
python main.py
```

---

## 🛠️ Bot Commands & Features

- **`/start`** — Welcome screen and guided 20-second student profile builder (Major, Year, Dorm, Interests, Social Handle).
- **`/find`** — Join the queue and pair with another student anonymously.
- **`/next`** — Skip to the next student instantly.
- **`/stop`** — End the active chat or leave the queue.
- **`/reveal`** — Mutually exchange student profile cards and Telegram/IG handles (only shared when both students agree).
- **`/meet`** — Suggest a random campus spot (Library lounge, Quad, Cafe) with an icebreaker prompt.
- **`/report`** — Report and permanently block an inappropriate user.
- **`/profile`** — View and edit student details.

---

## 📂 File Architecture

| File | Description |
|---|---|
| `main.py` | Main Telegram Bot runtime, queue matching engine, anonymous message relay, and cloud health check |
| `database.py` | PostgreSQL connection pool (Neon / Supabase) with SQLite fallback |
| `config.py` | Campus locations, icebreakers, interest list, and defaults |
| `requirements.txt` | Python packages (`python-telegram-bot`, `asyncpg`, `aiohttp`, etc.) |
| `render.yaml` | Render Blueprint deployment config |
| `Procfile` | Cloud process specification (`web` and `worker`) |
| `schema.sql` | SQL table schemas for students, chat logs, and safety reports |
| `Dockerfile` | Container configuration for Docker / VPS deployments |
