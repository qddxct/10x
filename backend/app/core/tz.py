"""Beijing-time helpers.

The DB stores naive datetimes interpreted as Asia/Shanghai.  All
application code MUST use :func:`now_beijing` instead of
``datetime.utcnow()`` so that persisted timestamps match the DB
time-zone setting (``+08:00``).
"""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

BEIJING = ZoneInfo("Asia/Shanghai")


def now_beijing() -> datetime:
    """Return current Beijing time as a timezone-naive datetime."""
    return datetime.now(BEIJING).replace(tzinfo=None)


def today_beijing():
    """Return today's date in Beijing time."""
    return now_beijing().date()
