import os
import datetime
import state
from fyers_apiv3.FyersWebsocket import data_ws
from config import CLIENT_ID, CURRENT_CONFIG, IST, MAX_CONSECUTIVE_SL, PHASE_NAMES
from execution.trade import execute_order, trigger_entry, update_trailing_sl
from utils.logger import log_trade_exit

# ==========================================
# 6. WEBSOCKET
# ==========================================
def on_message(msg):
    if not isinstance(msg, dict) or 'ltp' not in msg or 'symbol' not in msg:
        return

    ltp = msg.get('ltp') or msg.get('last_traded_price')
    symbol = msg.get('symbol')
    if not ltp or not symbol:
        return

    # --- A. EXIT LOGIC (with trailing SL + cooldown tracking) ---
    for t_type in ['CE', 'PE']:
        trade = state.active_trades[t_type]
        if trade and symbol == trade['symbol']:

            # Step 1: Update trailing SL before checking exit
            update_trailing_sl(trade, ltp)

            # Step 2: Check exit conditions
            exit_signal = False
            reason = ""

            if ltp >= trade['target']:
                exit_signal = True
                reason = "TARGET"
            elif ltp <= trade['sl']:
                exit_signal = True
                if trade['trail_phase'] > 0:
                    reason = f"TRAIL_SL_P{trade['trail_phase']}"
                else:
                    reason = "SL"

            if exit_signal:
                phase_name = PHASE_NAMES.get(trade['trail_phase'], '?')
                print(f"\nCLOSING {t_type} ({reason}) @ {ltp} x {trade['qty']} | Phase: {phase_name}")
                print(f"   Entry: {trade['entry']} | Peak: {round(trade['peak'],2)} | Final SL: {trade['sl']}")
                execute_order(trade['symbol'], "SELL", trade['qty'])
                pnl = (ltp - trade['entry']) * trade['qty']
                log_trade_exit(trade['id'], ltp, reason, pnl,
                               trade['qty'], trade['trail_phase'], trade['peak'], trade['sl'])

                if reason == "SL":
                    state.last_sl_time[t_type] = datetime.datetime.now(IST)
                    state.consecutive_sl[t_type] += 1
                    print(f"  Consec {t_type} SLs: {state.consecutive_sl[t_type]}/{MAX_CONSECUTIVE_SL}")
                    if state.consecutive_sl[t_type] >= MAX_CONSECUTIVE_SL:
                        print(f"  >>> {t_type} BLOCKED for today")
                elif reason.startswith("TRAIL_SL"):
                    state.last_sl_time[t_type] = datetime.datetime.now(IST)
                elif reason == "TARGET":
                    state.consecutive_sl[t_type] = 0
                    print(f"  Consec {t_type} SL counter reset (TARGET)")

                state.active_trades[t_type] = None
            return

    # --- B. ENTRY LOGIC ---
    if symbol == CURRENT_CONFIG["SYMBOL"]:
        if state.alert_setup['CE']:
            if ltp > state.alert_setup['CE']['trigger']:
                trigger_entry("CE", ltp, state.alert_setup['CE']['timestamp'])
                state.alert_setup['CE'] = None
            elif ltp < state.alert_setup['CE']['sl']:
                print("CE Setup Invalidated")
                state.alert_setup['CE'] = None

        if state.alert_setup['PE']:
            if ltp < state.alert_setup['PE']['trigger']:
                trigger_entry("PE", ltp, state.alert_setup['PE']['timestamp'])
                state.alert_setup['PE'] = None
            elif ltp > state.alert_setup['PE']['sl']:
                print("PE Setup Invalidated")
                state.alert_setup['PE'] = None

def start_socket():
    try:
        def on_open():
            print("WebSocket Connected")
            state.fyers_ws.subscribe(
                symbols=[CURRENT_CONFIG["SYMBOL"]], data_type="SymbolUpdate"
            )
            state.fyers_ws.keep_running()

        state.fyers_ws = data_ws.FyersDataSocket(
            access_token=f"{CLIENT_ID}:{state.access_token}",
            log_path=os.getcwd(),
            litemode=False,
            write_to_file=False,
            reconnect=True,
            on_connect=on_open,
            on_message=on_message,
            on_error=lambda e: print("WS ERROR:", e),
            on_close=lambda e: print("WS CLOSED:", e)
        )
        state.fyers_ws.connect()
    except Exception as e:
        print("Socket Crash:", e)
