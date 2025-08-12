# backend/db.py
import sqlite3
from config import DB_PATH

def init_db():
    with sqlite3.connect(DB_PATH) as con:
        cur = con.cursor()
        cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY,
            telegram_id INTEGER UNIQUE,
            wallet TEXT,
            ref_code TEXT UNIQUE,
            referrer_id INTEGER,
            accepted_terms INTEGER DEFAULT 0,
            active INTEGER DEFAULT 0,
            mode TEXT DEFAULT 'test',
            exchange TEXT NULL,
            api_key TEXT NULL,
            api_secret TEXT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )""")
        cur.execute("""
        CREATE TABLE IF NOT EXISTS payments (
            id INTEGER PRIMARY KEY,
            user_id INTEGER,
            amount INTEGER, -- cents
            ref TEXT,
            status TEXT DEFAULT 'pending', -- pending | paid
            tx_hash TEXT,
            token_address TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            paid_on TIMESTAMP NULL
        )""")
        cur.execute("""
        CREATE TABLE IF NOT EXISTS rewards (
            id INTEGER PRIMARY KEY,
            referrer_user_id INTEGER,
            referred_user_id INTEGER,
            amount INTEGER,
            status TEXT DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )""")
        con.commit()

def db_execute(query, params=()):
    with sqlite3.connect(DB_PATH) as con:
        cur = con.cursor()
        cur.execute(query, params)
        con.commit()
        return cur

def db_fetchone(query, params=()):
    with sqlite3.connect(DB_PATH) as con:
        cur = con.cursor()
        cur.execute(query, params)
        return cur.fetchone()

def db_fetchall(query, params=()):
    with sqlite3.connect(DB_PATH) as con:
        cur = con.cursor()
        cur.execute(query, params)
        return cur.fetchall()
