# backend/listener.py
import asyncio
import json
from web3 import Web3
from web3.middleware import geth_poa_middleware
from web3._utils.filters import Filter
from config import WEB3_WS, CONTRACT_ADDRESS, CONTRACT_ABI_PATH
from backend.db import db_fetchone, db_execute
from aiogram import Bot
from config import BOT_TOKEN, ADMIN_ID

# helper to normalise hex -> int
def to_int(x):
    try:
        return int(x)
    except:
        return None

async def start_listener(aiogram_bot: Bot):
    if not WEB3_WS:
        print("WEB3_WS not configured, listener disabled")
        return

    print("Listener: connecting to web3 ws...", WEB3_WS)
    w3 = Web3(Web3.WebsocketProvider(WEB3_WS, websocket_timeout=60))
    # If your chain is POA-style (some testnets), inject middleware
    try:
        w3.middleware_onion.inject(geth_poa_middleware, layer=0)
    except Exception:
        pass

    with open(CONTRACT_ABI_PATH, "r") as f:
        abi = json.load(f)

    contract = w3.eth.contract(address=Web3.to_checksum_address(CONTRACT_ADDRESS), abi=abi)

    # Try to create filter for PaymentReceived (change name if different)
    try:
        event_filter = contract.events.PaymentReceived.createFilter(fromBlock='latest')
        print("Listener: event filter created for PaymentReceived")
    except Exception as e:
        print("Listener: failed to create filter (check ABI/event name). Error:", e)
        return

    while True:
        try:
            # get_new_entries is blocking; run in thread
            entries = await asyncio.to_thread(event_filter.get_new_entries)
            for ev in entries:
                # ev structure: {'args': {...}, 'event': 'PaymentReceived', 'transactionHash': b'...'}
                args = ev.get('args', {})
                tx_hash = ev.get('transactionHash').hex() if ev.get('transactionHash') else None
                payer = args.get('payer') or args.get('from') or args.get('sender')
                amount = args.get('amount') or args.get('value')
                ref = args.get('ref') or args.get('paymentId') or args.get('refCode')

                print("Listener: got event payer=%s amount=%s ref=%s tx=%s" % (payer, amount, ref, tx_hash))

                if ref:
                    # find pending payment with this ref
                    row = db_fetchone("SELECT id, user_id, status FROM payments WHERE ref = ?", (str(ref),))
                    if row and row[2] != 'paid':
                        pid = row[0]
                        db_execute("UPDATE payments SET status = 'paid', tx_hash = ?, paid_on = CURRENT_TIMESTAMP WHERE id = ?", (tx_hash, pid))
                        # optionally activate user and create reward
                        urow = db_fetchone("SELECT referrer_id FROM users WHERE id = ?", (row[1],))
                        referrer = urow[0] if urow else None
                        if referrer:
                            # reward 10%
                            amount_int = to_int(amount) if amount is not None else 0
                            reward = (amount_int * 10) // 100
                            db_execute("INSERT INTO rewards (referrer_user_id, referred_user_id, amount, status) VALUES (?, ?, ?, 'pending')", (referrer, row[1], reward))
                        # notify admin
                        await aiogram_bot.send_message(ADMIN_ID, f"Платёж #{pid} подтверждён. tx: {tx_hash}")
        except Exception as e:
            print("Listener loop error:", e)
            await asyncio.sleep(5)

        await asyncio.sleep(2)
