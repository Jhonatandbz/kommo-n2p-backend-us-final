
import re
from datetime import datetime
import pytz

US_E164 = re.compile(r"^\+1\d{10}$")

def is_valid_us_e164(number: str) -> bool:
    return bool(US_E164.match(number))

def within_quiet_hours_et(now: datetime | None = None, start_hour=8, end_hour=21) -> bool:
    tz = pytz.timezone("America/New_York")
    now = now.astimezone(tz) if now else datetime.now(tz)
    return not (start_hour <= now.hour < end_hour)
