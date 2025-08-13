from backend.db import get_connection

# Заглушка для отправки токенов — здесь надо будет интегрировать web3 для реальных платежей
def send_tokens(to_address: str, amount: float):
    print(f"Send {amount} tokens to {to_address}")

def payout():
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM users")
    users = c.fetchall()

    for user in users:
        # допустим, 100 токенов — базовая сумма
        base_amount = 100.0

        # Если есть реферер — 10% ему
        referrer_code = user["referrer_code"]
        if referrer_code:
            c.execute("SELECT wallet_address FROM users WHERE referral_code = ?", (referrer_code,))
            referrer = c.fetchone()
            if referrer:
                referrer_wallet = referrer["wallet_address"]
                send_tokens(referrer_wallet, base_amount * 0.1)
                send_tokens(user["wallet_address"], base_amount * 0.9)
            else:
                send_tokens(user["wallet_address"], base_amount)
        else:
            send_tokens(user["wallet_address"], base_amount)
    conn.close()

if __name__ == "__main__":
    payout()
