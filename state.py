# Global State
fyers_api = None
fyers_ws = None
access_token = None

alert_setup = {'CE': None, 'PE': None}
active_trades = {'CE': None, 'PE': None}
last_setup_candle = {'CE': None, 'PE': None}

eod_done = False
gap_detected = False
gap_info = {}

# Risk Management State
last_sl_time = {'CE': None, 'PE': None}
consecutive_sl = {'CE': 0, 'PE': 0}
daily_trade_count = {'CE': 0, 'PE': 0}

# Daily reset tracker
_last_reset_date = None

# Candle dedup tracker
_last_scanned_candle = None
