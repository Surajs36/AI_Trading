import time
import datetime
import pandas as pd
import state
from config import CURRENT_CONFIG, GAP_RESUME_HOUR, GAP_RESUME_MINUTE, IST

def detect_gap():
    """
    Compare today's open with previous day's close.
    Sets gap_detected = True if gap exceeds threshold.
    Called once per day during 9:15-9:25 IST window.
    """
    if state.gap_detected:
        return

    now_ist = datetime.datetime.now(IST)
    market_open = now_ist.replace(hour=9, minute=15, second=0, microsecond=0)
    check_cutoff = now_ist.replace(hour=9, minute=25, second=0, microsecond=0)

    if now_ist < market_open or now_ist > check_cutoff:
        return

    try:
        to_time = int(time.time())
        from_time = to_time - (7 * 86400)
        data = {
            "symbol": CURRENT_CONFIG["SYMBOL"],
            "resolution": "D",
            "date_format": "0",
            "range_from": from_time,
            "range_to": to_time,
            "cont_flag": "1"
        }
        resp = state.fyers_api.history(data)

        if 'candles' not in resp or len(resp['candles']) < 2:
            print("GAP CHECK: Not enough daily data -- skipping")
            return

        df = pd.DataFrame(resp['candles'],
                          columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='s')

        prev_close = df.iloc[-2]['close']
        today_open = df.iloc[-1]['open']

        gap = today_open - prev_close
        gap_abs = abs(gap)
        gap_direction = "UP" if gap > 0 else "DOWN"
        threshold = CURRENT_CONFIG.get("GAP_THRESHOLD", 250)

        print(f"\n{'='*50}")
        print(f"GAP CHECK -- {CURRENT_CONFIG['SYMBOL']}")
        print(f"   Prev Close : {prev_close}")
        print(f"   Today Open : {today_open}")
        print(f"   Gap        : {round(gap, 2)} pts ({gap_direction})")
        print(f"   Threshold  : {threshold} pts")

        if gap_abs > threshold:
            state.gap_detected = True
            state.gap_info = {
                'direction': gap_direction,
                'size': round(gap_abs, 2),
                'prev_close': prev_close,
                'today_open': today_open,
                'threshold': threshold
            }
            for t_type in ['CE', 'PE']:
                if state.alert_setup[t_type]:
                    print(f"   Cleared stale {t_type} setup (overnight)")
                    state.alert_setup[t_type] = None
            print(f"   BIG GAP {gap_direction}! ({round(gap_abs, 2)} > {threshold} pts)")
            print(f"   PAUSED UNTIL {GAP_RESUME_HOUR}:{GAP_RESUME_MINUTE:02d} IST")
        else:
            print(f"   Gap within limits ({round(gap_abs, 2)} < {threshold}) -- normal trading")

        print(f"{'='*50}\n")

    except Exception as e:
        print(f"GAP CHECK ERROR: {e}")
