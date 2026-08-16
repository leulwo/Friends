import re

with open("database.py", "r") as f:
    content = f.read()

# Add age, last_active to PG schema
content = content.replace(
    "social_handle TEXT,",
    "social_handle TEXT,\n                            age TEXT DEFAULT 'Not specified',\n                            last_active TIMESTAMP DEFAULT CURRENT_TIMESTAMP,"
)

# Add alter table for PG
content = content.replace(
    "await conn.execute(\"ALTER TABLE students ADD COLUMN IF NOT EXISTS photo_id TEXT;\")",
    """await conn.execute("ALTER TABLE students ADD COLUMN IF NOT EXISTS photo_id TEXT;")
                        await conn.execute("ALTER TABLE students ADD COLUMN IF NOT EXISTS age TEXT DEFAULT 'Not specified';")
                        await conn.execute("ALTER TABLE students ADD COLUMN IF NOT EXISTS last_active TIMESTAMP DEFAULT CURRENT_TIMESTAMP;")"""
)

# Add age, last_active to SQLite schema
content = content.replace(
    "social_handle TEXT,\n                photo_id TEXT,",
    "social_handle TEXT,\n                photo_id TEXT,\n                age TEXT DEFAULT 'Not specified',\n                last_active DATETIME DEFAULT CURRENT_TIMESTAMP,"
)

# Add alter table for SQLite
content = content.replace(
    """        try:
            cur.execute("ALTER TABLE students ADD COLUMN photo_id TEXT;")
        except Exception:
            pass""",
    """        try:
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
            pass"""
)

# Update save_user
content = content.replace(
    "username = data.get(\"username\", \"\")",
    "username = data.get(\"username\", \"\")\n        age = data.get(\"age\", \"Not specified\")"
)

content = content.replace(
    "INSERT INTO students (user_id, username, full_name, gender, preferred_gender, major, study_year, dorm, interests, bio, social_handle, photo_id)",
    "INSERT INTO students (user_id, username, full_name, gender, preferred_gender, major, study_year, dorm, interests, bio, social_handle, photo_id, age)"
)
content = content.replace(
    "VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)",
    "VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13)"
)
content = content.replace(
    "photo_id = EXCLUDED.photo_id;",
    "photo_id = EXCLUDED.photo_id,\n                        age = EXCLUDED.age;"
)
content = content.replace(
    "user_id, username, name, gender, preferred_gender, major, year, dorm, interests, bio, handle, photo_id)",
    "user_id, username, name, gender, preferred_gender, major, year, dorm, interests, bio, handle, photo_id, age)"
)

content = content.replace(
    "INSERT OR REPLACE INTO students (user_id, username, full_name, gender, preferred_gender, major, study_year, dorm, interests, bio, social_handle, photo_id)",
    "INSERT OR REPLACE INTO students (user_id, username, full_name, gender, preferred_gender, major, study_year, dorm, interests, bio, social_handle, photo_id, age)"
)
content = content.replace(
    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
)


# Add update_activity method
update_activity_code = """
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
"""

content = content.replace(
    "async def update_preference",
    update_activity_code + "\n    async def update_preference"
)

# Update find_candidates signature and logic
content = content.replace(
    "async def find_candidates(self, user_id: int, gender_filter: str = \"Any\", exclude_ids: Optional[Set[int]] = None) -> List[dict]:",
    "async def find_candidates(self, user_id: int, gender_filter: str = \"Any\", exclude_ids: Optional[Set[int]] = None, current_user_profile: dict = None) -> List[dict]:"
)

content = content.replace("LIMIT 20", "LIMIT 50")

# Advanced matching sorting logic at the end of find_candidates
sorting_logic = """
        # Advanced Matching Algorithm: Score and Sort Candidates
        if current_user_profile and rows:
            my_major = current_user_profile.get("major", "")
            my_year = current_user_profile.get("study_year", "")
            my_dorm = current_user_profile.get("dorm", "")
            my_interests_str = current_user_profile.get("interests", "")
            my_interests = set([i.strip().lower() for i in my_interests_str.split(",") if i.strip()])
            
            for row in rows:
                score = 0
                # Same Major (+3 points)
                if row.get("major") == my_major and my_major and my_major != "Undeclared":
                    score += 3
                # Same Year (+1 point)
                if row.get("study_year") == my_year and my_year:
                    score += 1
                # Same Dorm (+1 point)
                if row.get("dorm") == my_dorm and my_dorm:
                    score += 1
                # Shared Interests (+2 points per match)
                their_interests_str = row.get("interests", "")
                their_interests = set([i.strip().lower() for i in their_interests_str.split(",") if i.strip()])
                common = my_interests.intersection(their_interests)
                score += len(common) * 2
                
                # Active recently bonus could go here (relying on DB sort for now)
                
                row['match_score'] = score
                
            # Sort by match_score DESC, total_chats ASC (to balance), then we can pick top
            rows.sort(key=lambda x: (x.get('match_score', 0), -x.get('total_chats', 0)), reverse=True)
            
        return rows[:20]  # Return top 20 best matches
"""

content = re.sub(r"return rows\s*$", sorting_logic, content, flags=re.MULTILINE)


with open("database.py", "w") as f:
    f.write(content)

print("DB Patched!")
