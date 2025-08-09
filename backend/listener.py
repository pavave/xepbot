# backend/listener.py
import os
import asyncio
from web3 import Web3
from sqlalchemy import text
from backend.db import engine
from dotenv import load_dotenv
load_dotenv()

RPC_WS = os.getenv('RPC_WS')
CONTRACT_ADDRESS = Web3.toChecksumAddress(os.getenv('CONTRACT_ADDRESS'))
ABI = [
    {
      "anonymous": False,
      "inputs": [
        {"indexed": True, "internalType": "address", "name": "payer", "type": "address"},
        {"indexed": False, "internalType": "uint256", "name": "amount", "type": "uint256"},
        {"indexed": False, "internalType": "string", "name": "reference", "type": "string"}
      ],
      "name": "Paid",
      "type": "event"
    }
]

w3 = Web3(Web3.WebsocketProvider(RPC_WS))
contract = w3.eth.contract(address=CONTRACT_ADDRESS, abi=ABI)


def handle_event(event):
    payer = event['args']['payer']
    amount = event['args']['amount']
    reference = event['args']['reference']
    tx_hash = event['transactionHash'].hex()
    print("Received Paid event:", payer, amount, reference)
    with engine.connect() as conn:
        res = conn.execute(text(
            "INSERT INTO payments (tx_hash, payer_address, amount, reference, status) VALUES (:tx, :payer, :amt, :ref, 'pending') RETURNING id"
        ), {"tx": tx_hash, "payer": payer, "amt": amount, "ref": reference})
        payment_id = res.scalar_one()
        conn.commit()
        # try to match user by eth_address
        user = conn.execute(text("SELECT id, referrer_id FROM users WHERE LOWER(eth_address)=LOWER(:addr)"), {"addr": payer}).first()
        if user:
            user_id = user.id
            conn.execute(text("UPDATE payments SET user_id=:uid, status='processed' WHERE id=:pid"), {"uid": user_id, "pid": payment_id})
            conn.commit()
            referrer_id = user.referrer_id
            if referrer_id:
                ref_pct = int(os.getenv('REF_PERCENT', '10'))
                reward = (int(amount) * ref_pct) // 100
                conn.execute(text("INSERT INTO referrals (referrer_user_id, referred_user_id, amount, status) VALUES (:rid, :uid, :amt, 'pending')"), {"rid": referrer_id, "uid": user_id, "amt": reward})
                conn.commit()
        else:
            print("Payment from unknown address:", payer)


async def log_loop(event_filter, poll_interval):
    while True:
        for event in event_filter.get_new_entries():
            handle_event(event)
        await asyncio.sleep(poll_interval)


async def main_loop():
    event_filter = contract.events.Paid.createFilter(fromBlock='latest')
    await log_loop(event_filter, 2)


if __name__ == '__main__':
    asyncio.run(main_loop())
