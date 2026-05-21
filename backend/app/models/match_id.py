"""Logical match-ID helpers.

A logical match id is a 12-digit BIGINT that encodes:

- ``YYYYMMDD`` — the 竞彩 **business day** in Beijing time (URL 的 ``d`` 参数).
- ``W``        — weekday digit (周日=0, 周一=1, …, 周六=6).
- ``NNN``      — the 3-digit 竞彩 sequence number (from 周X###).

Example: the Sunday match 周日001 on 2026-04-19 has id ``202604190001``.

Both 竞彩 (sporttery.cn) and 球探 (jc.titan007.com) surface the same
业务日 + 周X + 编号 triple, so this logical id is a **natural cross-source key**
and is used as the PRIMARY KEY of ``sporttery_matches``.

Weekday convention (Chinese 竞彩 style):
    周日=0, 周一=1, 周二=2, 周三=3, 周四=4, 周五=5, 周六=6
"""

from __future__ import annotations

import re
from datetime import date, datetime, timedelta

_JC_CODE_RE = re.compile(r"^周([日一二三四五六])(\d{3})$")

# 周日=0 per 竞彩 convention; maps Chinese character → weekday digit
_CN_WEEKDAY: dict[str, int] = {
    "日": 0,
    "一": 1,
    "二": 2,
    "三": 3,
    "四": 4,
    "五": 5,
    "六": 6,
}


def weekday_digit (d: date) -> int:
    """Return 竞彩-style weekday digit (0=Sun, 1=Mon, …, 6=Sat)."""
    return d.isoweekday() % 7


def parse_jc_code (code: str) -> tuple[int, int] | None:
    """Parse a 竞彩编号 string like ``周日001`` → ``(weekday_digit, seq)``.

    Returns ``None`` when the code does not match the expected pattern.
    """
    if not code:
        return None
    match = _JC_CODE_RE.match(code.strip())
    if not match:
        return None
    weekday_char, seq_str = match.groups()
    return _CN_WEEKDAY[weekday_char], int(seq_str)


def build_logical_id (business_date: date, weekday: int, seq: int) -> int:
    """Assemble the 12-digit logical id.

    Validates that ``weekday`` matches ``business_date``'s weekday digit —
    otherwise raises ``ValueError`` since a mismatch means the caller picked
    the wrong business day.
    """
    expected = weekday_digit(business_date)
    if weekday != expected:
        raise ValueError(
            f"weekday digit {weekday} does not match business_date "
            f"{business_date.isoformat()} (expected {expected})"
        )
    if not (0 <= seq <= 999):
        raise ValueError(f"seq {seq} out of range 0..999")
    return int(f"{business_date:%Y%m%d}{weekday}{seq:03d}")


def logical_id_from_jc (business_date: date, jc_code: str) -> int | None:
    """Convenience: combine ``business_date`` + 竞彩编号 → logical id."""
    parsed = parse_jc_code(jc_code)
    if parsed is None:
        return None
    weekday, seq = parsed
    return build_logical_id(business_date, weekday, seq)


def infer_business_date (kickoff: datetime, weekday: int) -> date:
    """Infer the 竞彩 business date given a ``kickoff`` datetime and the
    weekday digit from 竞彩编号.

    Kickoffs after midnight (02:00 etc.) still belong to the previous
    business day, so we walk back up to 6 days looking for the matching
    weekday.
    """
    kickoff_date = kickoff.date()
    for back in range(0, 7):
        candidate = kickoff_date - timedelta(days=back)
        if weekday_digit(candidate) == weekday:
            return candidate
    raise ValueError(
        f"cannot infer business date for kickoff={kickoff.isoformat()} weekday={weekday}"
    )


def logical_id_from_kickoff (kickoff: datetime, jc_code: str) -> int | None:
    """Build a logical id from kickoff datetime and 竞彩编号 (e.g. ``周日001``).

    Returns ``None`` when ``jc_code`` does not match the expected pattern.
    """
    parsed = parse_jc_code(jc_code)
    if parsed is None:
        return None
    weekday, seq = parsed
    business_date = infer_business_date(kickoff, weekday)
    return build_logical_id(business_date, weekday, seq)


def split_logical_id (logical_id: int) -> tuple[date, int, int]:
    """Decompose a 12-digit logical id into ``(business_date, weekday, seq)``.

    Raises ``ValueError`` for malformed ids.
    """
    s = str(logical_id)
    if len(s) != 12:
        raise ValueError(f"logical_id must be 12 digits, got {logical_id!r}")
    y, m, d = int(s[0:4]), int(s[4:6]), int(s[6:8])
    weekday = int(s[8])
    seq = int(s[9:12])
    return date(y, m, d), weekday, seq
