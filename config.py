# config.py
import os
from dotenv import load_dotenv
load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))
WEB3_WS = os.getenv("WEB3_WS")
WEB3_HTTP = os.getenv("WEB3_HTTP")
CONTRACT_ADDRESS = os.getenv("CONTRACT_ADDRESS")
USDC_ADDRESS = os.getenv("USDC_ADDRESS")
CONTRACT_ABI_PATH = os.getenv("CONTRACT_ABI_PATH", "contracts/MinimalPaymentReceiver.json")
DB_PATH = os.getenv("DB_PATH", "xepbot.sqlite")
FERNET_KEY = os.getenv("FERNET_KEY")

