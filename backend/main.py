# backend/main.py
from fastapi import FastAPI
from pydantic import BaseModel
from backend.db import engine
from sqlalchemy import text
import os
from dotenv import load_dotenv
load_dotenv()

app = FastAPI()

class RegisterRequest(BaseModel):
    telegram_id: int
    eth_address: str
    ref_code: str | None = None

@app.post('/register')
async def register(req: RegisterRequest):
    with engine.connect() as conn:
        referrer = None
        if req.ref_code:
            r = conn.execute(text("SELECT id FROM users WHERE id=:id"), {"id": int(req.ref_code)}).first()
            if r:
                referrer = r.id
        conn.execute(text("INSERT INTO users (telegram_id, eth_address, referrer_id) VALUES (:tg, :eth, :ref) ON CONFLICT (telegram_id) DO UPDATE SET eth_address = EXCLUDED.eth_address"), {"tg": req.telegram_id, "eth": req.eth_address, "ref": referrer})
        conn.commit()
    return {"ok": True}

@app.get('/status/{telegram_id}')
async def status(telegram_id: int):
    with engine.connect() as conn:
        r = conn.execute(text("SELECT license_status FROM users WHERE telegram_id=:tg"), {"tg": telegram_id}).first()
        if not r:
            return {"license_status": "not_registered"}
        return {"license_status": r.license_status}
