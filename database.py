import sqlite3
import os

DB_PATH = os.environ.get("MESSENGER_DB", "messenger.db")


def get_db_path():
    return os.environ.get("MESSENGER_DB", "messenger.db")


def get_connection():
    conn = sqlite3.connect(get_db_path())
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    with get_connection() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                id   TEXT PRIMARY KEY,
                name TEXT NOT NULL UNIQUE
            );

            CREATE TABLE IF NOT EXISTS conversations (
                id         TEXT PRIMARY KEY,
                type       TEXT NOT NULL DEFAULT 'direct',
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS conversation_members (
                conversation_id TEXT NOT NULL,
                user_id         TEXT NOT NULL,
                PRIMARY KEY (conversation_id, user_id),
                FOREIGN KEY (conversation_id) REFERENCES conversations(id),
                FOREIGN KEY (user_id)         REFERENCES users(id)
            );

            CREATE TABLE IF NOT EXISTS messages (
                id              TEXT PRIMARY KEY,
                conversation_id TEXT NOT NULL,
                sender_id       TEXT NOT NULL,
                text            TEXT NOT NULL,
                status          TEXT NOT NULL DEFAULT 'sent',
                created_at      TEXT NOT NULL,
                FOREIGN KEY (conversation_id) REFERENCES conversations(id),
                FOREIGN KEY (sender_id)       REFERENCES users(id)
            );

            CREATE INDEX IF NOT EXISTS idx_messages_conv
                ON messages(conversation_id, created_at);
        """)
        conn.commit()
