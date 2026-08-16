-- =========================================================
-- DATABASE SCHEMA: Free Neon / Supabase PostgreSQL or SQLite
-- =========================================================

CREATE TABLE IF NOT EXISTS students (
    user_id BIGINT PRIMARY KEY,
    username TEXT,
    full_name TEXT NOT NULL,
    gender TEXT DEFAULT 'Not specified',
    preferred_gender TEXT DEFAULT 'Any',
    major TEXT DEFAULT 'Undeclared',
    study_year TEXT DEFAULT 'Undergraduate',
    dorm TEXT DEFAULT 'Campus',
    interests TEXT DEFAULT '',
    bio TEXT DEFAULT '',
    social_handle TEXT,
    is_banned BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    total_chats INT DEFAULT 0
);

CREATE TABLE IF NOT EXISTS chat_logs (
    id SERIAL PRIMARY KEY,
    user_1 BIGINT NOT NULL,
    user_2 BIGINT NOT NULL,
    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    ended_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS reports (
    id SERIAL PRIMARY KEY,
    reporter_id BIGINT NOT NULL,
    reported_id BIGINT NOT NULL,
    reason TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_students_interests ON students(interests);
CREATE INDEX IF NOT EXISTS idx_chat_users ON chat_logs(user_1, user_2);
