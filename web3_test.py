# web3_test.py — быстрый тест: соединение, price, последние события Paid
import os, json
from web3 import Web3
from dotenv import load_dotenv

load_dotenv()

WEB3_HTTP = os.getenv("WEB3_HTTP")
WEB3_WS = os.getenv("WEB3_WS")
CONTRACT_ADDRESS = os.getenv("CONTRACT_ADDRESS")
CONTRACT_ABI_PATH = os.getenv("CONTRACT_ABI_PATH", "contracts/MinimalPaymentReceiver.json")

provider_url = WEB3_HTTP or WEB3_WS
if not provider_url:
    raise RuntimeError("Установи WEB3_HTTP или WEB3_WS в .env")

w3 = Web3(Web3.HTTPProvider(provider_url))
print("Connected:", w3.is_connected())
try:
    print("Chain id:", w3.eth.chain_id)
except Exception as e:
    print("Can't read chain id:", e)

# load ABI
if not os.path.exists(CONTRACT_ABI_PATH):
    raise FileNotFoundError(f"ABI not found at {CONTRACT_ABI_PATH}")

with open(CONTRACT_ABI_PATH, "r", encoding="utf-8") as f:
    abi = json.load(f)

contract = w3.eth.contract(address=Web3.to_checksum_address(CONTRACT_ADDRESS), abi=abi)

# read price
try:
    price = contract.functions.price().call()
    print("Contract price (token units):", price)
except Exception as e:
    print("Failed to read price():", e)

# try a small recent-events scan (last 5000 blocks)
try:
    latest = w3.eth.block_number
    from_block = max(0, latest - 5000)
    print(f"Scanning Paid events from block {from_block} to {latest} ...")
    # prefer get_logs for reliability
    event_abi = None
    for item in abi:
        if item.get("type") == "event" and item.get("name") == "Paid":
            event_abi = item
            break
    if event_abi is None:
        print("Paid event ABI not found in ABI")
    else:
        topic = w3.sha3(text="Paid(address,uint256,bytes32)").hex()
        # better to use contract.events if available
        try:
            evs = contract.events.Paid().get_logs(fromBlock=from_block, toBlock=latest)
            print("Events found via contract.events.Paid():", len(evs))
            for ev in evs[:5]:
                print("  payer:", ev['args'].get('payer'), " amount:", ev['args'].get('amount'), " ref:", ev['args'].get('paymentReference'))
        except Exception as e:
            # fallback to raw logs (less convenient)
            print("contract.events.Paid get_logs failed:", e)
            logs = w3.eth.get_logs({
                "fromBlock": from_block,
                "toBlock": latest,
                "address": Web3.to_checksum_address(CONTRACT_ADDRESS)
            })
            print("Raw logs count:", len(logs))
except Exception as e:
    print("Events scan failed:", e)
