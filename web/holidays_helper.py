from datetime import date, datetime, timedelta
import holidays
from web.server import GERMAN_HOLIDAY_NAMES

def get_holidays_for_period(start_date, end_date):
    """
    Returns a list of holiday dicts for the given period (inclusive).
    Each dict contains: name (German), start_utc, end_utc, tags, is_holiday.
    """
    # Ensure dates are date objects
    if isinstance(start_date, datetime):
        start_date = start_date.date()
    if isinstance(end_date, datetime):
        end_date = end_date.date()
    de_ni = holidays.country_holidays('DE', subdiv='NI', years=range(start_date.year, end_date.year + 1))
    out = []
    for d, name in sorted(de_ni.items()):
        if start_date <= d <= end_date:
            name_de = GERMAN_HOLIDAY_NAMES.get(name, name)
            out.append({
                'name': name_de,
                'start_utc': datetime(d.year, d.month, d.day, 0, 0, 0),
                'end_utc': datetime(d.year, d.month, d.day, 23, 59, 59),
                'tags': ['holiday'],
                'is_holiday': True,
            })
    return out
