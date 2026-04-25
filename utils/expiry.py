import datetime
from config import CURRENT_CONFIG, IST
from utils.holidays import is_trading_holiday, NSE_HOLIDAYS

# ==========================================
# 2. EXPIRY LOGIC
# ==========================================
def get_expiry_details(target_weekday):
    """
    Calculate expiry date and Fyers symbol code.
    Automatically shifts expiry to previous trading day if it falls on an NSE holiday.
    Uses `holidays` library — no hardcoded dates needed.
    """
    now = datetime.datetime.now(IST)
    today_date = now.date()

    # 1. Calculate the initial target expiry day (e.g., next Tuesday)
    days_ahead = target_weekday - today_date.weekday()
    if days_ahead < 0:
        days_ahead += 7

    # If it's expiry day but after 3:30 PM, look at next week
    if days_ahead == 0 and now.time() > datetime.time(15, 30):
        days_ahead += 7

    raw_expiry_date = today_date + datetime.timedelta(days=days_ahead)
    next_expiry_date = raw_expiry_date

    # 2. DYNAMIC SHIFT: If expiry falls on holiday, move to previous trading day
    while next_expiry_date in NSE_HOLIDAYS or next_expiry_date.weekday() >= 5:
        holiday_name = NSE_HOLIDAYS.get(next_expiry_date, "Weekend")
        print(f"EXPIRY SHIFT: {next_expiry_date.strftime('%a %d-%b')} is "
              f"'{holiday_name}' -> shifting back...")
        next_expiry_date -= datetime.timedelta(days=1)

    print(f"Confirmed Expiry: Raw={raw_expiry_date.strftime('%a %d-%b')} | "
          f"Actual={next_expiry_date.strftime('%a %d-%b')}")

    # 3. Determine monthly vs weekly
    date_next_week = raw_expiry_date + datetime.timedelta(days=7)
    is_monthly = raw_expiry_date.month != date_next_week.month

    # 4. Build Fyers symbol code
    year_str = str(next_expiry_date.year)[-2:]

    if is_monthly:
        month_str = next_expiry_date.strftime("%b").upper()
        expiry_code = f"{year_str}{month_str}"
    else:
        month = next_expiry_date.month
        month_map = {10: 'O', 11: 'N', 12: 'D'}
        m_code = month_map.get(month, str(month))
        day_str = f"{next_expiry_date.day:02d}"
        expiry_code = f"{year_str}{m_code}{day_str}"

    print(f"EXPIRY CODE: {expiry_code} | Monthly={is_monthly}")
    return expiry_code

def get_option_symbol(spot_price, trade_type):
    """Build full option symbol like NSE:NIFTY26421{strike}CE"""
    expiry_code = get_expiry_details(CURRENT_CONFIG["WEEKDAY"])
    step = CURRENT_CONFIG["STRIKE_STEP"]
    strike = int(round(spot_price / step) * step)
    symbol = f"{CURRENT_CONFIG['OPT_PREFIX']}{expiry_code}{strike}{trade_type}"
    print(f"OPTION SYMBOL: {symbol} (spot: {spot_price})")
    return symbol
