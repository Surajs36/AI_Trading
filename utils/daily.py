import datetime
import state
import utils.holidays
from config import IST

def daily_reset():
    """
    Reset all daily counters and flags at midnight IST.
    Called every scan cycle; triggers once when date changes.
    Also refreshes NSE holiday calendar when year changes.
    """
    today = datetime.datetime.now(IST).date()

    if state._last_reset_date == today:
        return  # Already reset today

    print(f"\n{'='*50}")
    print(f"DAILY RESET -- {today}")
    print(f"{'='*50}")

    # Refresh holiday calendar if year changed
    if state._last_reset_date is not None and state._last_reset_date.year != today.year:
        utils.holidays.NSE_HOLIDAYS = utils.holidays._load_nse_holidays()
        print(f"   Refreshed NSE holiday calendar for {today.year}")

    # Check if today is a trading holiday
    if utils.holidays.is_trading_holiday(today):
        holiday_name = utils.holidays.NSE_HOLIDAYS.get(today, "Weekend")
        print(f"   TODAY IS A TRADING HOLIDAY! ({holiday_name})")
        print(f"   Bot will skip trading.")

    state.eod_done = False
    state.gap_detected = False
    state.gap_info = {}
    state.alert_setup = {'CE': None, 'PE': None}
    state.last_setup_candle = {'CE': None, 'PE': None}
    state.last_sl_time = {'CE': None, 'PE': None}
    state.consecutive_sl = {'CE': 0, 'PE': 0}
    state.daily_trade_count = {'CE': 0, 'PE': 0}
    state._last_scanned_candle = None

    state._last_reset_date = today
    print(f"   All counters, flags, and setups cleared")
    print(f"   Bot ready for new trading day")
    print(f"{'='*50}\n")
