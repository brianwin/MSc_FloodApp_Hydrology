from datetime import datetime
from dateutil.parser import parse as dtparse

def parse_date(val):
    try:
        return datetime.strptime(val, '%Y-%m-%d').date() if val else None
    except Exception:
        return None

def parse_datetime(val):
    try:
        return dtparse(val) if val else None
    except Exception:
        return None