import hashlib

def generate_referral_code(telegram_id: int) -> str:
    # Возьмём sha256 от telegram_id и вернём первые 8 символов
    h = hashlib.sha256(str(telegram_id).encode()).hexdigest()
    return h[:8]

def save_referral(db_add_user_func, telegram_id, wallet_address, referrer_code=None):
    referral_code = generate_referral_code(telegram_id)
    db_add_user_func(telegram_id, wallet_address, referral_code, referrer_code)
    return referral_code

