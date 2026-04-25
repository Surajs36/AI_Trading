import datetime
import holidays
from config import IST

def _load_nse_holidays():
    """Load NSE financial holidays for current + next year."""
    current_year = datetime.datetime.now(IST).date().year
    years = [current_year, current_year + 1]
    try:
        nse_cal = holidays.financial_holidays('XNSE', years=years)
        print(f"Loaded XNSE financial holidays for {years}: {len(nse_cal)} dates")
        return nse_cal
    except Exception:
        pass
    try:
        nse_cal = holidays.financial_holidays('NSE', years=years)
        print(f"Loaded NSE financial holidays for {years}: {len(nse_cal)} dates")
        return nse_cal
    except Exception:
        pass
    print("WARNING: NSE financial calendar not found, using Indian public holidays")
    return holidays.India(years=years)

# Global holidays variable to be used
NSE_HOLIDAYS = _load_nse_holidays()

def is_trading_holiday(check_date):
    """
    Check if a given date is an NSE trading holiday or weekend.
    """
    if isinstance(check_date, datetime.datetime):
        check_date = check_date.date()

    if check_date.weekday() >= 5:
        return True

    return check_date in NSE_HOLIDAYS

def get_previous_trading_day(from_date):
    """
    Find the previous trading day (not a holiday or weekend).
    """
    if isinstance(from_date, datetime.datetime):
        from_date = from_date.date()

    prev_day = from_date - datetime.timedelta(days=1)

    for _ in range(10):
        if not is_trading_holiday(prev_day):
            return prev_day
        prev_day -= datetime.timedelta(days=1)

    return from_date - datetime.timedelta(days=1)
