import sys
import time
import threading
from fyers_apiv3 import fyersModel

import state
from config import get_token_from_ssm, CLIENT_ID, SELECTED_INDEX, TRADE_QTY
from strategy.scanner import scan_strategy
from strategy.gap import detect_gap
from websocket.fyers_ws import start_socket
from utils.daily import daily_reset
from execution.trade import eod_squareoff, sync_positions, adopt_external_trades

# ==========================================
# 8. MAIN EXECUTION
# ==========================================
def refresh_token():
    state.access_token = get_token_from_ssm()
    state.fyers_api = fyersModel.FyersModel(
        client_id=CLIENT_ID, token=state.access_token,
        is_async=False, log_path="/home/ssm-user/trading_bot/logs"
    )
    print("Token refreshed from SSM.")

def connect_fyers():
    state.access_token = get_token_from_ssm()
    try:
        state.fyers_api = fyersModel.FyersModel(
            client_id=CLIENT_ID, token=state.access_token,
            is_async=False, log_path="/home/ssm-user/trading_bot/logs"
        )
        resp = state.fyers_api.get_profile()
        if resp.get('code') == 200:
            print(f"API Connected. Trading: {SELECTED_INDEX} x {TRADE_QTY} qty")
            return True
        else:
            print(f"API Connection Failed! Fyers Response: {resp}")
    except Exception as e:
        print(f"API Connection Exception: {e}")
        print("HINT: If this says 'No such file or directory', make sure you created the logs folder: mkdir -p /home/ssm-user/trading_bot/logs")
    return False

def main():
    if not sys.stdout.line_buffering:
        sys.stdout = open(sys.stdout.fileno(), mode='w', buffering=1)
        sys.stderr = open(sys.stderr.fileno(), mode='w', buffering=1)

    connected = False
    for attempt in range(3):
        print(f"Connection attempt {attempt+1}/3...")
        if connect_fyers():
            connected = True
            break
        print(f"Attempt {attempt+1} failed. Retrying in 10s...")
        time.sleep(10)

    if not connected:
        print("FATAL: Could not connect after 3 attempts. Exiting.")
        sys.exit(1)

    t = threading.Thread(target=start_socket)
    t.daemon = True
    t.start()

    scan_count = 0
    try:
        while True:
            daily_reset()
            eod_squareoff()

            if not state.eod_done:
                detect_gap()
                scan_strategy()
                sync_positions()
                adopt_external_trades()
                scan_count += 1
                if scan_count % 360 == 0:
                    refresh_token()

            time.sleep(60)
    except KeyboardInterrupt:
        print("\nBot Stopped")

if __name__ == "__main__":
    main()
