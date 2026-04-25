import time
import datetime
import pandas as pd
import state
from config import CURRENT_CONFIG, TIMEFRAME, EMA_PERIOD, IST, COOLDOWN_MINUTES, MAX_CONSECUTIVE_SL, MAX_TRADES_PER_DIRECTION, EMA_SLOPE_CANDLES, GAP_RESUME_HOUR, GAP_RESUME_MINUTE
from utils.holidays import is_trading_holiday

def _in_cooldown(trade_type):
    if state.last_sl_time[trade_type] is None:
        return False
    elapsed = (datetime.datetime.now(IST) - state.last_sl_time[trade_type]).total_seconds() / 60
    if elapsed < COOLDOWN_MINUTES:
        remaining = int(COOLDOWN_MINUTES - elapsed)
        print(f"  {trade_type} COOLDOWN: {remaining} min left")
        return True
    return False

def scan_strategy():
    today = datetime.datetime.now(IST).date()
    if is_trading_holiday(today):
        return

    try:
        if state.gap_detected:
            now_ist = datetime.datetime.now(IST)
            resume_time = now_ist.replace(
                hour=GAP_RESUME_HOUR, minute=GAP_RESUME_MINUTE,
                second=0, microsecond=0
            )
            if now_ist < resume_time:
                return

        to_time = int(time.time())
        from_time = to_time - (5 * 86400)
        data = {
            "symbol": CURRENT_CONFIG["SYMBOL"],
            "resolution": TIMEFRAME,
            "date_format": "0",
            "range_from": from_time,
            "range_to": to_time,
            "cont_flag": "1"
        }
        resp = state.fyers_api.history(data)
        if 'candles' not in resp:
            return

        df = pd.DataFrame(resp['candles'],
                          columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='s') \
                          .dt.tz_localize('UTC').dt.tz_convert('Asia/Kolkata')
        df['ema'] = df['close'].ewm(span=EMA_PERIOD, adjust=False).mean()

        now = datetime.datetime.now(IST).replace(tzinfo=None)
        bucket = now.minute - (now.minute % 5)
        target_time = now.replace(minute=bucket, second=0, microsecond=0) \
                      - datetime.timedelta(minutes=5)

        df['ts_naive'] = df['timestamp'].dt.tz_localize(None)
        row = df[df['ts_naive'] >= target_time]
        if row.empty:
            return

        c_data = row.iloc[0]
        c = c_data['close']
        o = c_data['open']
        h = c_data['high']
        l = c_data['low']
        ema = c_data['ema']
        candle_time = c_data['timestamp']
        candle_key = candle_time.strftime('%Y-%m-%d %H:%M')

        if candle_key == state._last_scanned_candle:
            return
        state._last_scanned_candle = candle_key

        candle_idx = df.index.get_loc(c_data.name)
        if candle_idx >= EMA_SLOPE_CANDLES:
            ema_prev = df['ema'].iloc[candle_idx - EMA_SLOPE_CANDLES]
            ema_slope = ema - ema_prev
        else:
            ema_slope = 0

        print(f"Scan {CURRENT_CONFIG['SYMBOL']} {candle_time.strftime('%H:%M')} "
              f"| C:{c} O:{o} H:{h} L:{l} | EMA:{round(ema,2)} "
              f"| Slope:{round(ema_slope,2)}")

        if c < o and l > ema:
            if ema_slope > 0:
                print(f"  PE SKIP: EMA rising (+{round(ema_slope,2)}) -- counter-trend")
            elif state.consecutive_sl['PE'] >= MAX_CONSECUTIVE_SL:
                print(f"  PE BLOCK: {state.consecutive_sl['PE']} consecutive SLs")
            elif state.daily_trade_count['PE'] >= MAX_TRADES_PER_DIRECTION:
                print(f"  PE BLOCK: max daily trades ({MAX_TRADES_PER_DIRECTION})")
            elif _in_cooldown('PE'):
                pass
            elif state.active_trades['PE'] is None and state.alert_setup['PE'] is None:
                if candle_key != state.last_setup_candle['PE']:
                    print(f"  PE SETUP! Trigger < {l} | Slope: {round(ema_slope,2)}")
                    state.alert_setup['PE'] = {
                        'trigger': l, 'sl': h, 'timestamp': candle_time
                    }
                    state.last_setup_candle['PE'] = candle_key

        if c > o and h < ema:
            if ema_slope < 0:
                print(f"  CE SKIP: EMA falling ({round(ema_slope,2)}) -- counter-trend")
            elif state.consecutive_sl['CE'] >= MAX_CONSECUTIVE_SL:
                print(f"  CE BLOCK: {state.consecutive_sl['CE']} consecutive SLs")
            elif state.daily_trade_count['CE'] >= MAX_TRADES_PER_DIRECTION:
                print(f"  CE BLOCK: max daily trades ({MAX_TRADES_PER_DIRECTION})")
            elif _in_cooldown('CE'):
                pass
            elif state.active_trades['CE'] is None and state.alert_setup['CE'] is None:
                if candle_key != state.last_setup_candle['CE']:
                    print(f"  CE SETUP! Trigger > {h} | Slope: {round(ema_slope,2)}")
                    state.alert_setup['CE'] = {
                        'trigger': h, 'sl': l, 'timestamp': candle_time
                    }
                    state.last_setup_candle['CE'] = candle_key

    except Exception as e:
        print(f"Scan Error: {e}")
