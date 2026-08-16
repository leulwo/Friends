import logging
import sqlite3
from typing import Optional

try:
    import asyncpg
    HAS_ASYNCPG = True
except ImportError:
    HAS_ASYNCPG = False

logger = logging.getLogger(__name__)

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
                
                # Aiven / Neon / Supabase cloud PostgreSQL connection
                try:
                    self.pg_pool = await asyncpg.create_pool(fixed_url, max_size=10)
                except Exception:
                    # Fallback for cloud providers requiring explicit SSL
                    import ssl
                    ssl_ctx = ssl.create_default_context()
                    ssl_ctx.check_hostname = False
                    ssl_ctx.verify_mode = ssl.CERT_NONE
                    # Remove query params that asyncpg might choke on
                    base_url = fixed_url.split("?")[0]
                    self.pg_pool = await asyncpg.create_pool(base_url, ssl=ssl_ctx, max_size=10)

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
                logger.info("Connected to PostgreSQL Database (Aiven/Cloud) successfully.")
                return
            except Exception as e:
                logger.error(f"PostgreSQL connection failed: {e}. Falling back to SQLite.")
                self.is_postgres = False

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
        logger.info(f"Initialized SQLite Database at {self.sqlite_file}.")

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
