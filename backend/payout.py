# backend/payout.py
import os
from web3 import Web3
from backend.db import engine
from sqlalchemy import text
from dotenv import load_dotenv
load_dotenv()

RPC = os.getenv('RPC_HTTP')
w3 = Web3(Web3.HTTPProvider(RPC))
PRIVATE_KEY = os.getenv('PRIVATE_KEY')
MY_ADDRESS = w3.toChecksumAddress(os.getenv('OWNER_ADDRESS'))
USDC_ADDRESS = w3.toChecksumAddress(os.getenv('USDC_ADDRESS'))
CHAIN_ID = int(os.getenv('CHAIN_ID', '42161'))

ERC20_ABI = [
    {
      "constant": False,
      "inputs": [
        {"name": "_to", "type": "address"},
        {"name": "_value", "type": "uint256"}
      ],
      "name": "transfer",
      "outputs": [{"name": "", "type": "bool"}],
      "type": "function"
    }
]

token = w3.eth.contract(address=USDC_ADDRESS, abi=ERC20_ABI)


def get_pending_payouts():
    with engine.connect() as conn:
        rows = conn.execute(text("SELECT r.referrer_user_id, u.eth_address as to_address, SUM(r.amount) as total_amount FROM referrals r JOIN users u ON u.id = r.referrer_user_id WHERE r.status = 'pending' GROUP BY r.referrer_user_id, u.eth_address")).all()
        return rows


def send_transfer(to_addr, amount):
    nonce = w3.eth.get_transaction_count(MY_ADDRESS)
    tx = token.functions.transfer(w3.toChecksumAddress(to_addr), int(amount)).buildTransaction({
        "chainId": CHAIN_ID,
        "gas": 120000,
        "gasPrice": w3.eth.gas_price,
        "nonce": nonce
    })
    signed = w3.eth.account.sign_transaction(tx, PRIVATE_KEY)
    txh = w3.eth.send_raw_transaction(signed.rawTransaction)
    return txh.hex()


def run_payout():
    rows = get_pending_payouts()
    if not rows:
        print('No pending payouts')
        return
    for r in rows:
        to_addr = r.to_address
        total_amount = int(r.total_amount)
        if total_amount == 0:
            continue
        with engine.connect() as conn:
            res = conn.execute(text("INSERT INTO payouts (referrer_user_id, amount, status) VALUES (:rid, :amt, 'queued') RETURNING id"), {"rid": r.referrer_user_id, "amt": total_amount})
            payout_id = res.scalar_one()
            conn.commit()
        try:
            txh = send_transfer(to_addr, total_amount)
            with engine.connect() as conn:
                conn.execute(text("UPDATE payouts SET tx_hash=:tx, status='sent' WHERE id=:pid"), {"tx": txh, "pid": payout_id})
                conn.execute(text("UPDATE referrals SET status='paid' WHERE referrer_user_id=:rid AND status='pending'"), {"rid": r.referrer_user_id})
                conn.commit()
            print(f"Paid {total_amount} to {to_addr}, tx {txh}")
        except Exception as e:
            print('Payment failed:', e)
            with engine.connect() as conn:
                conn.execute(text("UPDATE payouts SET status='failed' WHERE id=:pid"), {"pid": payout_id})
                conn.commit()

if __name__ == '__main__':
    run_payout()
