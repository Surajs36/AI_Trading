import os
import csv
import datetime
from config import TRADE_LOG_FILE, IST

# ==========================================
# 4. CSV LOGGING (v1 detailed format)
# ==========================================
def log_trade_entry(trade):
    file_exists = os.path.isfile(TRADE_LOG_FILE)
    
    # Ensure directory exists
    log_dir = os.path.dirname(TRADE_LOG_FILE)
    if log_dir and not os.path.exists(log_dir):
        os.makedirs(log_dir, exist_ok=True)
        
    try:
        with open(TRADE_LOG_FILE, mode='a', newline='') as file:
            writer = csv.writer(file)
            if not file_exists:
                writer.writerow(["TradeID", "Date", "Symbol", "Type", "Qty", "Entry", "Risk",
                                 "OrigSL", "OrigTarget", "Exit", "ExitQty", "Time",
                                 "Status", "TrailPhase", "PeakPrice", "FinalSL", "PnL"])
            writer.writerow([
                trade['id'], trade['entry_time'], trade['symbol'], trade['type'],
                trade['qty'], trade['entry'], trade['risk'],
                trade['sl'], trade['target'],
                0, 0, "", "OPEN", 0, 0, 0, 0
            ])
        print(f"Logged Entry: {trade['symbol']} x {trade['qty']}")
    except Exception as e:
        print(f"CSV Error: {e}")

def log_trade_exit(trade_id, exit_price, reason, pnl, exit_qty=0, trail_phase=0, peak=0, final_sl=0):
    try:
        rows = []
        with open(TRADE_LOG_FILE, 'r') as file:
            rows = list(csv.reader(file))
        for row in rows:
            if len(row) > 0 and row[0] == trade_id:
                row[9] = exit_price
                row[10] = exit_qty
                row[11] = datetime.datetime.now(IST).strftime("%H:%M:%S")
                row[12] = reason
                row[13] = trail_phase
                row[14] = peak
                row[15] = final_sl
                row[16] = round(pnl, 2)
                break
        with open(TRADE_LOG_FILE, 'w', newline='') as file:
            writer = csv.writer(file)
            writer.writerows(rows)
        print(f"Logged Exit: {reason} | PnL {round(pnl, 2)} | Qty: {exit_qty} | Phase: {trail_phase}")
    except Exception as e:
        print(f"CSV Update Error: {e}")
