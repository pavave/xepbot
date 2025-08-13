import sqlite3
from typing import Optional

DB_PATH = "xepbot.sqlite"

def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_connection()
    c = conn.cursor()
    c.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        telegram_id INTEGER UNIQUE,
        wallet_address TEXT UNIQUE,
        referral_code TEXT UNIQUE,
        referrer_code TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)
    conn.commit()
    conn.close()

def add_user(telegram_id: int, wallet_address: str, referral_code: str, referrer_code: Optional[str] = None):
    conn = get_connection()
    c = conn.cursor()
    try:
        c.execute(
            "INSERT INTO users (telegram_id, wallet_address, referral_code, referrer_code) VALUES (?, ?, ?, ?)",
            (telegram_id, wallet_address, referral_code, referrer_code)
        )
        conn.commit()
    except sqlite3.IntegrityError:
        # пользователь уже есть
        pass
    finally:
        conn.close()

def get_user_by_telegram_id(telegram_id: int) -> Optional[sqlite3.Row]:
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE telegram_id = ?", (telegram_id,))
    user = c.fetchone()
    conn.close()
    return user

def get_user_by_referral_code(referral_code: str) -> Optional[sqlite3.Row]:
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE referral_code = ?", (referral_code,))
    user = c.fetchone()
    conn.close()
    return user
