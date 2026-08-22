import logging
import sqlite3
import random
from typing import Optional, List, Set

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
                    base_url = fixed_url.split("?")[0]
                    self.pg_pool = await asyncpg.create_pool(base_url, ssl=ssl_ctx, max_size=10)

                async with self.pg_pool.acquire() as conn:
                    await conn.execute("""
                        CREATE TABLE IF NOT EXISTS students (
                            user_id BIGINT PRIMARY KEY,
                            username TEXT,
                            full_name TEXT,
                            gender TEXT DEFAULT 'Not specified',
                            preferred_gender TEXT DEFAULT 'Any',
                            major TEXT DEFAULT 'Undeclared',
                            study_year TEXT DEFAULT 'Undergrad',
                            dorm TEXT DEFAULT 'Campus',
                            interests TEXT DEFAULT '',
                            bio TEXT DEFAULT '',
                            social_handle TEXT,
                            age TEXT DEFAULT 'Not specified',
                            last_active TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            photo_id TEXT,
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
                    # Alter table if existing from older schema
                    try:
                        await conn.execute("ALTER TABLE students ADD COLUMN IF NOT EXISTS gender TEXT DEFAULT 'Not specified';")
                        await conn.execute("ALTER TABLE students ADD COLUMN IF NOT EXISTS preferred_gender TEXT DEFAULT 'Any';")
                        await conn.execute("ALTER TABLE students ADD COLUMN IF NOT EXISTS photo_id TEXT;")
                        await conn.execute("ALTER TABLE students ADD COLUMN IF NOT EXISTS age TEXT DEFAULT 'Not specified';")
                        await conn.execute("ALTER TABLE students ADD COLUMN IF NOT EXISTS last_active TIMESTAMP DEFAULT CURRENT_TIMESTAMP;")
                    except Exception as err:
                        logger.debug(f"Schema alter notice (PG): {err}")
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
                gender TEXT DEFAULT 'Not specified',
                preferred_gender TEXT DEFAULT 'Any',
                major TEXT DEFAULT 'Undeclared',
                study_year TEXT DEFAULT 'Undergrad',
                dorm TEXT DEFAULT 'Campus',
                interests TEXT DEFAULT '',
                bio TEXT DEFAULT '',
                social_handle TEXT,
                            age TEXT DEFAULT 'Not specified',
                            last_active TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                photo_id TEXT,
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
        # Safe migration for existing SQLite DBs
        try:
            cur.execute("ALTER TABLE students ADD COLUMN gender TEXT DEFAULT 'Not specified';")
        except Exception:
            pass
        try:
            cur.execute("ALTER TABLE students ADD COLUMN preferred_gender TEXT DEFAULT 'Any';")
        except Exception:
            pass
        try:
            cur.execute("ALTER TABLE students ADD COLUMN photo_id TEXT;")
        except Exception:
            pass
        try:
            cur.execute("ALTER TABLE students ADD COLUMN age TEXT DEFAULT 'Not specified';")
        except Exception:
            pass
        try:
            cur.execute("ALTER TABLE students ADD COLUMN last_active DATETIME DEFAULT CURRENT_TIMESTAMP;")
        except Exception:
            pass
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
        age = data.get("age", "Not specified")
        name = data.get("name") or data.get("full_name") or "Fellow Student"
        gender = data.get("gender", "Not specified")
        preferred_gender = data.get("preferred_gender", "Any")
        major = data.get("major", "Undeclared")
        year = data.get("year") or data.get("study_year") or "Undergrad"
        dorm = data.get("dorm", "Campus")
        interests = ",".join(data.get("interests", [])) if isinstance(data.get("interests"), list) else data.get("interests", "")
        bio = data.get("bio", "Hey! Excited to meet people around campus.")
        handle = f"@{username}" if username else "Not shared"
        photo_id = data.get("photo_id")

        if self.is_postgres and self.pg_pool:
            async with self.pg_pool.acquire() as conn:
                await conn.execute("""
                    INSERT INTO students (user_id, username, full_name, gender, preferred_gender, major, study_year, dorm, interests, bio, social_handle, photo_id, age)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13)
                    ON CONFLICT (user_id) DO UPDATE SET
                        username = EXCLUDED.username,
                        full_name = EXCLUDED.full_name,
                        gender = EXCLUDED.gender,
                        preferred_gender = EXCLUDED.preferred_gender,
                        major = EXCLUDED.major,
                        study_year = EXCLUDED.study_year,
                        dorm = EXCLUDED.dorm,
                        interests = EXCLUDED.interests,
                        bio = EXCLUDED.bio,
                        social_handle = EXCLUDED.social_handle,
                        photo_id = EXCLUDED.photo_id,
                        age = EXCLUDED.age;
                """, user_id, username, name, gender, preferred_gender, major, year, dorm, interests, bio, handle, photo_id, age)
        else:
            conn = sqlite3.connect(self.sqlite_file)
            cur = conn.cursor()
            cur.execute("""
                INSERT OR REPLACE INTO students (user_id, username, full_name, gender, preferred_gender, major, study_year, dorm, interests, bio, social_handle, photo_id, age)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (user_id, username, name, gender, preferred_gender, major, year, dorm, interests, bio, handle, photo_id, age))
            conn.commit()
            conn.close()

    
    async def update_activity(self, user_id: int):
        if self.is_postgres and self.pg_pool:
            async with self.pg_pool.acquire() as conn:
                await conn.execute("UPDATE students SET last_active = CURRENT_TIMESTAMP WHERE user_id = $1", user_id)
        else:
            try:
                conn = sqlite3.connect(self.sqlite_file)
                cur = conn.cursor()
                cur.execute("UPDATE students SET last_active = CURRENT_TIMESTAMP WHERE user_id = ?", (user_id,))
                conn.commit()
                conn.close()
            except Exception:
                pass

    async def update_preference(self, user_id: int, preferred_gender: str):
        """Update student's preferred matching filter."""
        if self.is_postgres and self.pg_pool:
            async with self.pg_pool.acquire() as conn:
                await conn.execute("UPDATE students SET preferred_gender = $1 WHERE user_id = $2", preferred_gender, user_id)
        else:
            conn = sqlite3.connect(self.sqlite_file)
            cur = conn.cursor()
            cur.execute("UPDATE students SET preferred_gender = ? WHERE user_id = ?", (preferred_gender, user_id))
            conn.commit()
            conn.close()

    async def find_candidates(self, user_id: int, filter_type: str = "filter_any", exclude_ids: Optional[Set[int]] = None, current_user_profile: dict = None) -> List[dict]:
        """Find candidate student profiles matching the chosen filter and prioritized by traits."""
        exclude_list = list(exclude_ids or set())
        if user_id not in exclude_list:
            exclude_list.append(user_id)

        rows = []
        if self.is_postgres and self.pg_pool:
            async with self.pg_pool.acquire() as conn:
                if filter_type == "filter_female":
                    query = """
                        SELECT * FROM students 
                        WHERE is_banned = FALSE 
                          AND user_id != ALL($1) 
                          AND gender ILIKE '%female%'
                        ORDER BY last_active DESC NULLS LAST, RANDOM()
                        LIMIT 150
                    """
                    records = await conn.fetch(query, exclude_list)
                elif filter_type == "filter_male":
                    query = """
                        SELECT * FROM students 
                        WHERE is_banned = FALSE 
                          AND user_id != ALL($1) 
                          AND gender ILIKE '%male%' AND gender NOT ILIKE '%female%'
                        ORDER BY last_active DESC NULLS LAST, RANDOM()
                        LIMIT 150
                    """
                    records = await conn.fetch(query, exclude_list)
                else:
                    query = """
                        SELECT * FROM students 
                        WHERE is_banned = FALSE 
                          AND user_id != ALL($1)
                        ORDER BY last_active DESC NULLS LAST, RANDOM()
                        LIMIT 150
                    """
                    records = await conn.fetch(query, exclude_list)
                rows = [dict(r) for r in records]
        else:
            conn = sqlite3.connect(self.sqlite_file)
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            placeholders = ",".join(["?"] * len(exclude_list))
            
            if filter_type == "filter_female":
                query = f"""
                    SELECT * FROM students 
                    WHERE is_banned = 0 
                      AND user_id NOT IN ({placeholders})
                      AND gender LIKE '%female%'
                    ORDER BY last_active DESC, RANDOM()
                    LIMIT 150
                """
                cur.execute(query, exclude_list)
            elif filter_type == "filter_male":
                query = f"""
                    SELECT * FROM students 
                    WHERE is_banned = 0 
                      AND user_id NOT IN ({placeholders})
                      AND gender LIKE '%male%' AND gender NOT LIKE '%female%'
                    ORDER BY last_active DESC, RANDOM()
                    LIMIT 150
                """
                cur.execute(query, exclude_list)
            else:
                query = f"""
                    SELECT * FROM students 
                    WHERE is_banned = 0 
                      AND user_id NOT IN ({placeholders})
                    ORDER BY last_active DESC, RANDOM()
                    LIMIT 150
                """
                cur.execute(query, exclude_list)
            records = cur.fetchall()
            rows = [dict(r) for r in records]
            conn.close()

        
        # Advanced Matching Algorithm: Score and Sort Candidates
        if current_user_profile and rows:
            import re
            from datetime import datetime, timezone
            
            my_major = current_user_profile.get("major", "")
            my_year = current_user_profile.get("study_year", "")
            my_dorm = current_user_profile.get("dorm", "")
            my_interests_str = current_user_profile.get("interests", "")
            my_interests = set([i.strip().lower() for i in my_interests_str.split(",") if i.strip()])
            my_age_str = current_user_profile.get("age", "")
            my_age = int(re.sub(r'\D', '', my_age_str)) if re.sub(r'\D', '', my_age_str) else None
            
            for row in rows:
                score = 0
                
                # Online availability (+5 points if active in the last 24h)
                # Since we ordered by last_active DESC, they're already quite relevant.
                last_active = row.get("last_active")
                if last_active:
                    try:
                        if isinstance(last_active, str):
                            la_dt = datetime.strptime(last_active.split('.')[0], "%Y-%m-%d %H:%M:%S")
                        else:
                            la_dt = last_active
                        if la_dt.tzinfo is None:
                            la_dt = la_dt.replace(tzinfo=timezone.utc)
                        now_dt = datetime.now(timezone.utc)
                        hours_diff = (now_dt - la_dt).total_seconds() / 3600
                        if hours_diff <= 24:
                            score += 5
                        if hours_diff <= 1:
                            score += 5
                    except Exception:
                        pass
                
                # Same Major (+3 points)
                if row.get("major") == my_major and my_major and my_major != "Undeclared":
                    score += 3
                    if filter_type == "filter_major":
                        score += 20
                        
                # Same Year (+1 point)
                if row.get("study_year") == my_year and my_year:
                    score += 1
                    if filter_type == "filter_major":
                        score += 20
                        
                # Same Dorm (+1 point)
                if row.get("dorm") == my_dorm and my_dorm:
                    score += 1
                    
                # Shared Interests (+3 points per match)
                their_interests_str = row.get("interests", "")
                their_interests = set([i.strip().lower() for i in their_interests_str.split(",") if i.strip()])
                common = my_interests.intersection(their_interests)
                score += len(common) * 3
                if filter_type == "filter_interests" and len(common) > 0:
                    score += len(common) * 15
                
                # Similar Age (+3 points)
                their_age_str = row.get("age", "")
                their_age = int(re.sub(r'\D', '', their_age_str)) if re.sub(r'\D', '', their_age_str) else None
                if my_age and their_age and abs(my_age - their_age) <= 2:
                    score += 3
                    if filter_type == "filter_age":
                        score += 20
                elif my_age_str and my_age_str == their_age_str:
                    score += 2
                    if filter_type == "filter_age":
                        score += 20
                
                row['match_score'] = score
                
            # Sort by match_score DESC, total_chats ASC (to balance), then we can pick top
            rows.sort(key=lambda x: (x.get('match_score', 0), -x.get('total_chats', 0)), reverse=True)
            
        return rows[:20]  # Return top 20 best matches

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
