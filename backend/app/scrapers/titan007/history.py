"""Titan007 historical data parser.

Uses two internal handler endpoints to pull complete daily data:

- ``JcResult.aspx?d=YYYY-MM-DD`` — schedule + scores + 竞彩编号 (日期内全部赛事)
- ``oddsData.aspx?d=YYYY-MM-DD&cid=1&st=1`` — 澳门欧赔 + 亚盘 (同日全部赛事)

两路返回的 matchId 完全一致(titan007 内部 id), 可直接按 matchId join。

Response encoding is UTF-8 (not gb2312 as the HTML page header claims).

The parser here is pure (no I/O / DB); backfill orchestration lives in
:mod:`app.scripts.backfill`.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation

JC_RESULT_URL = "https://jc.titan007.com/handle/JcResult.aspx"
ODDS_DATA_URL = "https://jc.titan007.com/handle/oddsData.aspx"
ODDSLIST_JS_URL = "https://1x2d.titan007.com/{match_id}.js"
TITAN_HKJC_COMPANY_ID = "432"

JC_DEFAULT_HEADERS = {
    "Referer": "https://jc.titan007.com/schedule.aspx",
    "Accept-Language": "zh-CN,zh;q=0.9",
}

STATUS_FINISHED = "-1"


@dataclass(frozen=True)
class TitanLeague:
    sclassid: str
    name: str


@dataclass(frozen=True)
class TitanMatch:
    match_id: str
    kickoff: datetime
    status: str
    jc_code: str
    sclassid: str
    home_team: str
    away_team: str
    home_score: int | None
    away_score: int | None
    home_ht_score: int | None
    away_ht_score: int | None
    handicap_value: Decimal | None

    @property
    def is_finished(self) -> bool:
        return self.status == STATUS_FINISHED and self.home_score is not None


@dataclass(frozen=True)
class TitanOdds:
    match_id: str
    win_odds: Decimal | None
    draw_odds: Decimal | None
    lose_odds: Decimal | None
    handicap_value: Decimal | None
    win_handicap_odds: Decimal | None
    draw_handicap_odds: Decimal | None
    lose_handicap_odds: Decimal | None


def merge_titan_odds_by_priority(odds_groups: list[list[TitanOdds]]) -> list[TitanOdds]:
    """Merge bookmaker odds by priority, keeping the first odds for each match.

    The caller should pass groups in priority order, e.g. Macau first and
    fallback second. Existing primary odds are never overwritten by fallback odds.
    """
    merged: dict[str, TitanOdds] = {}
    for odds_list in odds_groups:
        for odds in odds_list:
            if odds.match_id not in merged:
                merged[odds.match_id] = odds
            else:
                merged[odds.match_id] = _fill_missing_odds_fields(
                    merged[odds.match_id], odds
                )
    return list(merged.values())


def _fill_missing_odds_fields(primary: TitanOdds, fallback: TitanOdds) -> TitanOdds:
    """Keep primary values, filling only missing fields from fallback."""
    return TitanOdds(
        match_id=primary.match_id,
        win_odds=primary.win_odds if primary.win_odds is not None else fallback.win_odds,
        draw_odds=(
            primary.draw_odds if primary.draw_odds is not None else fallback.draw_odds
        ),
        lose_odds=(
            primary.lose_odds if primary.lose_odds is not None else fallback.lose_odds
        ),
        handicap_value=(
            primary.handicap_value
            if primary.handicap_value is not None
            else fallback.handicap_value
        ),
        win_handicap_odds=(
            primary.win_handicap_odds
            if primary.win_handicap_odds is not None
            else fallback.win_handicap_odds
        ),
        draw_handicap_odds=(
            primary.draw_handicap_odds
            if primary.draw_handicap_odds is not None
            else fallback.draw_handicap_odds
        ),
        lose_handicap_odds=(
            primary.lose_handicap_odds
            if primary.lose_handicap_odds is not None
            else fallback.lose_handicap_odds
        ),
    )


def _dec(value: str | None) -> Decimal | None:
    if value is None or value == "":
        return None
    try:
        return Decimal(value)
    except InvalidOperation:
        return None


def _int(value: str | None) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except ValueError:
        return None


def _parse_ts(value: str) -> datetime | None:
    """Parse titan007's ``year,m,d,H,M,S`` timestamp.

    Note: titan007 uses JavaScript-style 0-indexed months (Jan=0, Dec=11),
    so we offset by +1 to reach normal calendar months.
    """
    if not value:
        return None
    parts = value.split(",")
    if len(parts) != 6:
        return None
    try:
        y, m, d, h, mi, s = (int(p) for p in parts)
        return datetime(y, m + 1, d, h, mi, s)
    except (ValueError, TypeError):
        return None


def _primary_name(raw: str) -> str:
    """The 3-variant team name cell is comma-separated: simp,tw,alt.

    We pick the first (simplified Chinese) variant.
    """
    if not raw:
        return ""
    return raw.split(",")[0].strip()


def parse_jc_result(text: str) -> tuple[list[TitanLeague], list[TitanMatch]]:
    """Parse JcResult.aspx body (UTF-8 decoded).

    Layout: ``<leagues>$<matches>$<extras>``, each section pipe-separated rows.
    """
    if not text:
        return [], []

    sections = text.split("$")
    leagues = _parse_leagues(sections[0] if sections else "")
    matches = _parse_matches(sections[1] if len(sections) >= 2 else "")
    return leagues, matches


def _parse_leagues(section: str) -> list[TitanLeague]:
    if not section:
        return []
    out: list[TitanLeague] = []
    for row in section.split("!"):
        if not row:
            continue
        fields = row.split("^")
        if len(fields) < 4:
            continue
        sclassid = fields[0].strip()
        name_cell = fields[3]
        name = _primary_name(name_cell)
        if sclassid and name:
            out.append(TitanLeague(sclassid=sclassid, name=name))
    return out


def _parse_matches(section: str) -> list[TitanMatch]:
    if not section:
        return []
    out: list[TitanMatch] = []
    for row in section.split("!"):
        if not row:
            continue
        fields = row.split("^")
        if len(fields) < 23:
            continue
        match_id = fields[0].strip()
        kickoff = _parse_ts(fields[1])
        if not match_id or kickoff is None:
            continue
        out.append(
            TitanMatch(
                match_id=match_id,
                kickoff=kickoff,
                status=fields[3].strip(),
                jc_code=fields[4].strip(),
                sclassid=fields[5].strip(),
                home_team=_primary_name(fields[8]),
                away_team=_primary_name(fields[10]),
                home_score=_int(fields[11]),
                away_score=_int(fields[12]),
                home_ht_score=_int(fields[13]),
                away_ht_score=_int(fields[14]),
                handicap_value=_dec(fields[22]) if len(fields) > 22 else None,
            )
        )
    return out


def parse_odds_data(text: str) -> list[TitanOdds]:
    """Parse oddsData.aspx body for a **real bookmaker** (cid != 105).

    Format: matches separated by ``$``; within each match sections
    separated by ``!``:

    - section[0]: matchId
    - section[1]: asian handicap — ``id^initLine^initH^initA^currLine^currH^currA``
    - section[2]: european odds — ``id^initD^initH^initA^currD^currH^currA``
      (Draw / HomeWin / AwayWin order — verified against 1x2.titan007.com)
    - section[3]: over/under — ``id^initLine^initO^initU^currLine^currO^currU``

    We extract the **current** (closing) values (indices 4-6) for both
    european and asian sections.
    """
    if not text:
        return []
    out: list[TitanOdds] = []
    for match_block in text.strip().split("$"):
        if not match_block:
            continue
        sections = match_block.split("!")
        if len(sections) < 3:
            continue
        match_id = sections[0].strip()
        if not match_id:
            continue

        asian_fields = sections[1].split("^") if len(sections) > 1 else []
        euro_fields = sections[2].split("^") if len(sections) > 2 else []

        draw_odds = _dec(euro_fields[4]) if len(euro_fields) > 6 else None
        win_odds = _dec(euro_fields[5]) if len(euro_fields) > 6 else None
        lose_odds = _dec(euro_fields[6]) if len(euro_fields) > 6 else None

        handicap_value = _dec(asian_fields[4]) if len(asian_fields) > 6 else None
        win_handicap_odds = _dec(asian_fields[5]) if len(asian_fields) > 6 else None
        lose_handicap_odds = _dec(asian_fields[6]) if len(asian_fields) > 6 else None

        out.append(
            TitanOdds(
                match_id=match_id,
                win_odds=win_odds,
                draw_odds=draw_odds,
                lose_odds=lose_odds,
                handicap_value=handicap_value,
                win_handicap_odds=win_handicap_odds,
                draw_handicap_odds=None,
                lose_handicap_odds=lose_handicap_odds,
            )
        )
    return out


def parse_oddslist_js_company(
    match_id: str,
    text: str,
    company_id: str,
) -> TitanOdds | None:
    """Parse one company row from Titan007 single-match European odds JS.

    The single-match JS uses ``var game=Array("...","...")``. For HKJC
    (company id 432), fields 10/11/12 are current Home/Draw/Away European odds.
    This source does not provide Asian handicap in the same row, so handicap
    fields are intentionally left empty.
    """
    if not text:
        return None

    for row in _extract_js_quoted_rows(text):
        fields = row.split("|")
        if len(fields) <= 12 or fields[0].strip() != company_id:
            continue
        return TitanOdds(
            match_id=match_id,
            win_odds=_dec(fields[10]),
            draw_odds=_dec(fields[11]),
            lose_odds=_dec(fields[12]),
            handicap_value=None,
            win_handicap_odds=None,
            draw_handicap_odds=None,
            lose_handicap_odds=None,
        )
    return None


def _extract_js_quoted_rows(text: str) -> list[str]:
    """Extract quoted row strings from Titan007's ``var game=Array(...)`` JS."""
    match = re.search(r"var\s+game\s*=\s*Array\((.*?)\);", text, re.DOTALL)
    if match is None:
        return []
    body = match.group(1)
    rows: list[str] = []
    for raw in re.findall(r'"((?:\\.|[^"\\])*)"', body):
        rows.append(
            raw.replace(r"\"", '"')
            .replace(r"\\", "\\")
            .replace(r"\/", "/")
        )
    return rows
