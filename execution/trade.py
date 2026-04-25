import time
import datetime
import state
from config import CURRENT_CONFIG, MAX_TRADES_PER_DIRECTION, IST, TRADE_QTY, ADOPT_DEFAULT_RISK, EOD_SQUAREOFF_HOUR, EOD_SQUAREOFF_MINUTE, PHASE_NAMES
from utils.expiry import get_option_symbol
from data.fyers_data import get_option_candle_data
from utils.logger import log_trade_entry, log_trade_exit
from utils.holidays import is_trading_holiday

# ==========================================
# 5. TRADING FUNCTIONS
# ==========================================
def execute_order(symbol, side, qty=0):
    print(f"Fetching Price for: {symbol} ({side} x {qty}) ...")
    try:
        q = state.fyers_api.quotes({"symbols": symbol})
        if 'd' in q and len(q['d']) > 0:
            data = q['d'][0]
            if 'v' in data and isinstance(data['v'], dict) and 'errmsg' in data['v']:
                print(f"API Error: {data['v']['errmsg']}")
                return 0
            filled_price = data['v']['lp']
            print(f"Filled at: {filled_price}")
            return filled_price
        else:
            print(f"Critical: Symbol not found. Raw: {q}")
            return 0
    except Exception as e:
        print(f"Exception in execution: {e}")
        return 0

def trigger_entry(trade_type, index_trigger_price, setup_timestamp):
    if state.active_trades[trade_type] is not None:
        return

    if state.eod_done:
        print(f"EOD done -- blocking {trade_type} entry")
        return

    today = datetime.datetime.now(IST).date()
    if is_trading_holiday(today):
        print(f"BLOCKED: Today ({today}) is a trading holiday")
        return

    if state.daily_trade_count[trade_type] >= MAX_TRADES_PER_DIRECTION:
        print(f"BLOCKED: Max {trade_type} trades ({MAX_TRADES_PER_DIRECTION}/day)")
        return

    opt_symbol = get_option_symbol(index_trigger_price, trade_type)
    print(f"EXECUTING {trade_type} ENTRY: {opt_symbol} x {TRADE_QTY}")

    entry_price = execute_order(opt_symbol, "BUY", TRADE_QTY)
    if entry_price == 0:
        print("Failed to get execution price.")
        return

    print(f"Fetching SL from Option Chart ({setup_timestamp.strftime('%H:%M')})...")
    opt_data = get_option_candle_data(opt_symbol, setup_timestamp)

    if opt_data:
        option_candle_low = opt_data['low']
        risk = entry_price - option_candle_low
        if risk <= 0:
            risk = 10
        dynamic_sl = option_candle_low
        dynamic_target = entry_price + (risk * 2)
    else:
        print("Warning: Option history failed. Using fallback SL.")
        risk = 20
        dynamic_sl = entry_price - 20
        dynamic_target = entry_price + 40

    trade_id = str(int(time.time()))
    new_trade = {
        "id": trade_id,
        "entry_time": datetime.datetime.now(IST).strftime("%Y-%m-%d %H:%M:%S"),
        "symbol": opt_symbol,
        "type": trade_type,
        "qty": TRADE_QTY,
        "entry": entry_price,
        "risk": risk,
        "sl": dynamic_sl,
        "target": dynamic_target,
        "orig_sl": dynamic_sl,
        "orig_target": dynamic_target,
        "peak": entry_price,
        "trail_phase": 0
    }

    state.active_trades[trade_type] = new_trade
    state.daily_trade_count[trade_type] += 1
    log_trade_entry(new_trade)
    state.fyers_ws.subscribe(symbols=[opt_symbol], data_type="SymbolUpdate")
    print(f"TRADE LIVE: {opt_symbol} x {TRADE_QTY} | Entry: {entry_price} "
          f"| SL: {round(dynamic_sl,2)} | TGT: {round(dynamic_target,2)} | Risk: {round(risk,2)}")
    print(f"  Daily {trade_type}: {state.daily_trade_count[trade_type]}/{MAX_TRADES_PER_DIRECTION} "
          f"| Consec SL: {state.consecutive_sl[trade_type]}")

# ==========================================
# 5B. POSITION SYNC
# ==========================================
def sync_positions():
    try:
        resp = state.fyers_api.positions()
        if resp.get('code') != 200 or 'netPositions' not in resp:
            return

        position_map = {}
        for pos in resp['netPositions']:
            position_map[pos['symbol']] = abs(pos.get('netQty', 0))

        for t_type in ['CE', 'PE']:
            trade = state.active_trades[t_type]
            if trade is None:
                continue

            actual_qty = position_map.get(trade['symbol'], 0)

            if actual_qty == 0:
                print(f"\nFULL MANUAL EXIT: {trade['symbol']} | All {trade['qty']} qty closed")
                try:
                    q = state.fyers_api.quotes({"symbols": trade['symbol']})
                    exit_price = q['d'][0]['v']['lp'] if 'd' in q and len(q['d']) > 0 else 0
                except:
                    exit_price = 0
                pnl = (exit_price - trade['entry']) * trade['qty'] if exit_price > 0 else 0
                log_trade_exit(trade['id'], exit_price, "MANUAL_EXIT", pnl,
                               trade['qty'], trade['trail_phase'], trade['peak'], trade['sl'])
                print(f"Cleaned up {t_type} trade. Estimated PnL: {round(pnl, 2)}")
                try:
                    state.fyers_ws.unsubscribe(symbols=[trade['symbol']])
                except:
                    pass
                state.active_trades[t_type] = None

            elif actual_qty < trade['qty']:
                sold_qty = trade['qty'] - actual_qty
                print(f"\nPARTIAL MANUAL EXIT: {trade['symbol']}")
                print(f"   You sold: {sold_qty} | Remaining: {actual_qty} (was {trade['qty']})")
                trade['qty'] = actual_qty

    except Exception as e:
        print(f"Position sync error: {e}")

# ==========================================
# 5C. TRAILING STOP LOSS
# ==========================================
def update_trailing_sl(trade, ltp):
    risk = trade['risk']
    entry = trade['entry']
    old_phase = trade['trail_phase']
    old_sl = trade['sl']

    if ltp > trade['peak']:
        trade['peak'] = ltp

    peak = trade['peak']
    profit_from_peak = peak - entry

    new_sl = trade['sl']
    new_phase = trade['trail_phase']

    if profit_from_peak >= risk * 1.0 and new_phase < 1:
        new_sl = entry
        new_phase = 1

    if profit_from_peak >= risk * 1.5 and new_phase < 2:
        new_sl = entry + (risk * 0.5)
        new_phase = 2

    if profit_from_peak >= risk * 2.0:
        trail_sl = peak - risk
        if trail_sl > new_sl:
            new_sl = trail_sl
        if new_phase < 3:
            new_phase = 3
            trade['target'] = float('inf')

    changed = False
    if new_sl > old_sl:
        trade['sl'] = round(new_sl, 2)
        changed = True

    if new_phase > old_phase:
        trade['trail_phase'] = new_phase
        print(f"\nTRAIL -> {PHASE_NAMES[new_phase]}: {trade['symbol']}")
        print(f"   SL: {round(old_sl,2)} -> {round(trade['sl'],2)} | Peak: {round(peak,2)} | Risk: {round(risk,2)}")
        if new_phase == 1:
            print(f"   No-loss trade! SL at entry {round(entry,2)}")
        elif new_phase == 2:
            print(f"   Profit locked! Min profit: {round(trade['sl'] - entry, 2)} pts")
        elif new_phase == 3:
            print(f"   TARGET REMOVED! Riding the runner. Trail: peak - {round(risk,2)}")
        changed = True
    elif changed and new_phase == 3:
        print(f"   Trail SL -> {round(trade['sl'],2)} (peak: {round(peak,2)})")

    return changed

# ==========================================
# 5D. EXTERNAL TRADE ADOPTION
# ==========================================
def adopt_external_trades():
    try:
        resp = state.fyers_api.positions()
        if resp.get('code') != 200 or 'netPositions' not in resp:
            return

        opt_prefix = CURRENT_CONFIG['OPT_PREFIX']
        tracked_symbols = set()
        for t_type in ['CE', 'PE']:
            if state.active_trades[t_type]:
                tracked_symbols.add(state.active_trades[t_type]['symbol'])

        for pos in resp['netPositions']:
            symbol = pos['symbol']
            net_qty = pos.get('netQty', 0)

            if not symbol.startswith(opt_prefix):
                continue
            if symbol in tracked_symbols:
                continue
            if net_qty <= 0:
                continue

            trade_type = None
            if symbol.endswith('CE'):
                trade_type = 'CE'
            elif symbol.endswith('PE'):
                trade_type = 'PE'
            else:
                continue

            if state.active_trades[trade_type] is not None:
                continue

            avg_price = pos.get('avgPrice', 0) or pos.get('buyAvg', 0)
            if avg_price <= 0:
                continue

            try:
                q = state.fyers_api.quotes({"symbols": symbol})
                current_ltp = q['d'][0]['v']['lp'] if 'd' in q and len(q['d']) > 0 else avg_price
            except:
                current_ltp = avg_price

            risk = ADOPT_DEFAULT_RISK
            sl = round(avg_price - risk, 2)
            target = round(avg_price + (risk * 2), 2)

            trade_id = f"EXT_{int(time.time())}"
            new_trade = {
                "id": trade_id,
                "entry_time": datetime.datetime.now(IST).strftime("%Y-%m-%d %H:%M:%S"),
                "symbol": symbol,
                "type": trade_type,
                "qty": net_qty,
                "entry": avg_price,
                "risk": risk,
                "sl": sl,
                "target": target,
                "orig_sl": sl,
                "orig_target": target,
                "peak": max(avg_price, current_ltp),
                "trail_phase": 0
            }

            state.active_trades[trade_type] = new_trade
            log_trade_entry(new_trade)
            state.fyers_ws.subscribe(symbols=[symbol], data_type="SymbolUpdate")
            print(f"\nADOPTED EXTERNAL TRADE: {symbol}")
            print(f"   Qty: {net_qty} | AvgPrice: {avg_price} | LTP: {current_ltp}")
            print(f"   SL: {sl} | TGT: {target} | Risk: {risk}")

    except Exception as e:
        print(f"External trade adoption error: {e}")

# ==========================================
# 5E. EOD AUTO-SQUAREOFF
# ==========================================
def eod_squareoff():
    if state.eod_done:
        return

    now_ist = datetime.datetime.now(IST)
    squareoff_time = now_ist.replace(
        hour=EOD_SQUAREOFF_HOUR, minute=EOD_SQUAREOFF_MINUTE,
        second=0, microsecond=0
    )

    if now_ist < squareoff_time:
        return

    print(f"\n{'='*50}")
    print(f"EOD AUTO-SQUAREOFF @ {now_ist.strftime('%H:%M:%S')} IST")
    print(f"{'='*50}")

    for t_type in ['CE', 'PE']:
        if state.alert_setup[t_type]:
            print(f"   Cancelled pending {t_type} setup")
            state.alert_setup[t_type] = None

    total_pnl = 0
    trades_closed = 0

    for t_type in ['CE', 'PE']:
        trade = state.active_trades[t_type]
        if trade is None:
            continue

        print(f"\n   Closing {t_type}: {trade['symbol']} x {trade['qty']}")
        exit_price = execute_order(trade['symbol'], "SELL", trade['qty'])

        if exit_price == 0:
            try:
                q = state.fyers_api.quotes({"symbols": trade['symbol']})
                exit_price = q['d'][0]['v']['lp'] if 'd' in q and len(q['d']) > 0 else 0
            except:
                exit_price = 0

        pnl = (exit_price - trade['entry']) * trade['qty'] if exit_price > 0 else 0
        total_pnl += pnl
        trades_closed += 1

        phase_name = PHASE_NAMES.get(trade['trail_phase'], '?')
        print(f"   Exit: {exit_price} | Entry: {trade['entry']} | Phase: {phase_name}")
        print(f"   PnL: {round(pnl, 2)} | Peak: {round(trade['peak'], 2)}")

        log_trade_exit(trade['id'], exit_price, "EOD_SQUAREOFF", pnl,
                       trade['qty'], trade['trail_phase'], trade['peak'], trade['sl'])

        try:
            state.fyers_ws.unsubscribe(symbols=[trade['symbol']])
        except:
            pass
        state.active_trades[t_type] = None

    print(f"\n{'='*50}")
    print(f"DAY SUMMARY -- {now_ist.strftime('%Y-%m-%d')}")
    print(f"   Trades closed at EOD: {trades_closed}")
    print(f"   Total EOD PnL: {round(total_pnl, 2)}")
    if trades_closed == 0:
        print(f"   No open trades at squareoff time")
    print(f"{'='*50}")
    print(f"\nNo new trades today. Will auto-reset at midnight.")

    state.eod_done = True
