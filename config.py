import os
import datetime
import boto3

# ==========================================
# 0. FETCH TOKEN FROM SSM
# ==========================================
ssm = boto3.client("ssm", region_name=os.environ.get("AWS_REGION", "us-east-1"))
PARAM_NAME = os.environ.get("FYERS_TOKEN_PARAM", "/fyers/access_token")

def get_token_from_ssm() -> str:
    try:
        resp = ssm.get_parameter(Name=PARAM_NAME, WithDecryption=True)
        token = resp["Parameter"]["Value"]
        print(f"Token fetched from SSM ({PARAM_NAME})")
        return token
    except Exception as e:
        print(f"FATAL: Could not fetch token from SSM: {e}")
        raise

# ==========================================
# 1. CONFIGURATION
# ==========================================
CLIENT_ID = os.environ.get("FYERS_CLIENT_ID", "6SYW748RMB-100")

IST = datetime.timezone(datetime.timedelta(hours=5, minutes=30))

INDEX_CONFIG = {
    "NIFTY": {
        "SYMBOL": "NSE:NIFTY50-INDEX",
        "OPT_PREFIX": "NSE:NIFTY",
        "WEEKDAY": 1,
        "LOT_SIZE": 75,
        "STRIKE_STEP": 50,
        "GAP_THRESHOLD": 250
    },
    "BANKNIFTY": {
        "SYMBOL": "NSE:NIFTYBANK-INDEX",
        "OPT_PREFIX": "NSE:BANKNIFTY",
        "WEEKDAY": 1,
        "LOT_SIZE": 15,
        "STRIKE_STEP": 100,
        "GAP_THRESHOLD": 500
    },
    "FINNIFTY": {
        "SYMBOL": "NSE:FINNIFTY-INDEX",
        "OPT_PREFIX": "NSE:FINNIFTY",
        "WEEKDAY": 1,
        "LOT_SIZE": 40,
        "STRIKE_STEP": 50,
        "GAP_THRESHOLD": 250
    },
    "SENSEX": {
        "SYMBOL": "BSE:SENSEX-INDEX",
        "OPT_PREFIX": "BSE:SENSEX",
        "WEEKDAY": 3,
        "LOT_SIZE": 20,
        "STRIKE_STEP": 100,
        "GAP_THRESHOLD": 800
    }
}

SELECTED_INDEX = os.environ.get("SELECTED_INDEX", "NIFTY")
CURRENT_CONFIG = INDEX_CONFIG[SELECTED_INDEX]
TIMEFRAME = "5"
EMA_PERIOD = 5
TRADE_LOG_FILE = "/home/ssm-user/trading_bot/real_bot/realtime_bot.csv"

# --- Quantity Config ---
TRADE_QTY = int(os.environ.get("TRADE_QTY", "75"))

# --- External Trade Adoption Config ---
ADOPT_DEFAULT_RISK = float(os.environ.get("ADOPT_DEFAULT_RISK", "20"))

# --- EOD Auto-Squareoff Config ---
EOD_SQUAREOFF_HOUR = int(os.environ.get("EOD_SQUAREOFF_HOUR", "15"))
EOD_SQUAREOFF_MINUTE = int(os.environ.get("EOD_SQUAREOFF_MINUTE", "25"))

# --- Gap Cooldown Config ---
GAP_RESUME_HOUR = int(os.environ.get("GAP_RESUME_HOUR", "12"))
GAP_RESUME_MINUTE = int(os.environ.get("GAP_RESUME_MINUTE", "0"))

# --- Risk Management Config ---
COOLDOWN_MINUTES = 15
MAX_CONSECUTIVE_SL = 2
MAX_TRADES_PER_DIRECTION = 3
EMA_SLOPE_CANDLES = 3

# --- Trailing SL Phase Names ---
PHASE_NAMES = {0: "ORIGINAL", 1: "BREAKEVEN", 2: "LOCK PROFIT", 3: "RUNNER"}
