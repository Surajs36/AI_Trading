import pandas as pd
from config import TIMEFRAME
import state

# ==========================================
# 3. OPTION CANDLE DATA
# ==========================================
def get_option_candle_data(opt_symbol, setup_timestamp):
    try:
        if hasattr(setup_timestamp, 'timestamp'):
            ts_epoch = int(setup_timestamp.timestamp())
        else:
            ts_epoch = int(setup_timestamp.replace(tzinfo=None).timestamp())

        from_time = ts_epoch - 600
        to_time = ts_epoch + 600

        data = {
            "symbol": opt_symbol,
            "resolution": TIMEFRAME,
            "date_format": "0",
            "range_from": from_time,
            "range_to": to_time,
            "cont_flag": "1"
        }
        resp = state.fyers_api.history(data)

        if 'candles' not in resp or len(resp['candles']) == 0:
            print(f"No candle data for {opt_symbol} at {setup_timestamp}")
            return None

        df = pd.DataFrame(resp['candles'],
                          columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='s') \
                          .dt.tz_localize('UTC').dt.tz_convert('Asia/Kolkata')
        df['ts_naive'] = df['timestamp'].dt.tz_localize(None)

        if hasattr(setup_timestamp, 'tzinfo') and setup_timestamp.tzinfo is not None:
            setup_naive = setup_timestamp.replace(tzinfo=None)
        else:
            setup_naive = setup_timestamp

        exact = df[df['ts_naive'] == setup_naive]
        if not exact.empty:
            row = exact.iloc[0]
        else:
            before = df[df['ts_naive'] <= setup_naive]
            if not before.empty:
                row = before.iloc[-1]
            else:
                row = df.iloc[0]

        candle = {
            'open': row['open'], 'high': row['high'],
            'low': row['low'],   'close': row['close']
        }
        print(f"Option candle for {opt_symbol}: "
              f"O:{candle['open']} H:{candle['high']} L:{candle['low']} C:{candle['close']}")
        return candle

    except Exception as e:
        print(f"Error fetching option candle: {e}")
        return None
