"""Titan007 match analysis page parser.

Fetches ``https://zq.titan007.com/analysis/{match_id}.htm`` (fallback:
``{match_id}cn.htm``) and extracts team statistics embedded in JavaScript
variables:

- ``h_data``  / ``a_data``  — recent match history (all venues)
- ``h2_data`` / ``a2_data`` — recent match history (home-only / away-only)
- ``v_data``               — head-to-head history

The resulting :class:`TitanTeamStats` contains pre-computed aggregates that
map directly to our ``sporttery_match_team_stats`` table columns.
"""

from __future__ import annotations

import ast
import logging
import re
import time
from dataclasses import dataclass

import httpx

logger = logging.getLogger(__name__)

ANALYSIS_URLS = (
    "https://zq.titan007.com/analysis/{match_id}cn.htm",
)

_HEADERS = {
    "Referer": "https://jc.titan007.com/",
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "Accept-Encoding": "gzip, deflate, br",
}

_SCRIPT_RE = re.compile(
    r"<[Ss][Cc][Rr][Ii][Pp][Tt][^>]*>(.*?)</[Ss][Cc][Rr][Ii][Pp][Tt]>",
    re.DOTALL,
)
_HTML_TAG_RE = re.compile(r"<[^>]+>")
_COLON_PATTERN = r"[:\N{FULLWIDTH COLON}]?"
_RANK_RE = re.compile(rf"排名{_COLON_PATTERN}.*?(\d+)$")


@dataclass(frozen=True)
class TitanTeamStats:
    home_rank: int | None
    home_season_wins: int
    home_season_draws: int
    home_season_losses: int
    home_home_wins: int
    home_home_draws: int
    home_home_losses: int
    home_recent_form: str | None
    away_rank: int | None
    away_season_wins: int
    away_season_draws: int
    away_season_losses: int
    away_away_wins: int
    away_away_draws: int
    away_away_losses: int
    away_recent_form: str | None
    h2h_home_wins: int | None
    h2h_draws: int | None
    h2h_away_wins: int | None
    home_recent_matches_count: int | None = None
    home_recent_goals_for: int | None = None
    home_recent_goals_against: int | None = None
    home_recent_goal_diff: int | None = None
    home_recent_win_by_1: int | None = None
    home_recent_win_by_2plus: int | None = None
    home_recent_loss_by_1: int | None = None
    home_recent_loss_by_2plus: int | None = None
    home_recent_draw_score_count: int | None = None
    home_recent_low_scoring_count: int | None = None
    home_recent_high_scoring_count: int | None = None
    away_recent_matches_count: int | None = None
    away_recent_goals_for: int | None = None
    away_recent_goals_against: int | None = None
    away_recent_goal_diff: int | None = None
    away_recent_win_by_1: int | None = None
    away_recent_win_by_2plus: int | None = None
    away_recent_loss_by_1: int | None = None
    away_recent_loss_by_2plus: int | None = None
    away_recent_draw_score_count: int | None = None
    away_recent_low_scoring_count: int | None = None
    away_recent_high_scoring_count: int | None = None
    home_home_recent_matches_count: int | None = None
    home_home_recent_goals_for: int | None = None
    home_home_recent_goals_against: int | None = None
    home_home_recent_goal_diff: int | None = None
    home_home_recent_win_by_1: int | None = None
    home_home_recent_win_by_2plus: int | None = None
    home_home_recent_loss_by_1: int | None = None
    home_home_recent_loss_by_2plus: int | None = None
    away_away_recent_matches_count: int | None = None
    away_away_recent_goals_for: int | None = None
    away_away_recent_goals_against: int | None = None
    away_away_recent_goal_diff: int | None = None
    away_away_recent_win_by_1: int | None = None
    away_away_recent_win_by_2plus: int | None = None
    away_away_recent_loss_by_1: int | None = None
    away_away_recent_loss_by_2plus: int | None = None
    h2h_matches_count: int | None = None
    h2h_home_goals_for: int | None = None
    h2h_home_goals_against: int | None = None
    h2h_goal_diff: int | None = None
    h2h_draw_score_count: int | None = None
    h2h_one_goal_margin_count: int | None = None
    h2h_low_scoring_count: int | None = None
    h2h_high_scoring_count: int | None = None


@dataclass(frozen=True)
class TitanScoreAgg:
    matches_count: int = 0
    goals_for: int = 0
    goals_against: int = 0
    goal_diff: int = 0
    win_by_1: int = 0
    win_by_2plus: int = 0
    loss_by_1: int = 0
    loss_by_2plus: int = 0
    draw_score_count: int = 0
    one_goal_margin_count: int = 0
    low_scoring_count: int = 0
    high_scoring_count: int = 0


def _clean_team_name(value: object) -> str:
    text = str(value or "").strip()
    return re.sub(r"\d+$", "", text).strip()


def _parse_int(value: object) -> int | None:
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return None


def _parse_score_from_row(row: list, target_team: str) -> tuple[int, int] | None:
    """Return goals for/against for ``target_team`` in one Titan history row."""
    if len(row) < 10:
        return None
    home_score = _parse_int(row[8])
    away_score = _parse_int(row[9])
    if home_score is None or away_score is None:
        return None

    target = _clean_team_name(target_team)
    row_home = _clean_team_name(row[5] if len(row) > 5 else "")
    row_away = _clean_team_name(row[7] if len(row) > 7 else "")
    if row_home == target:
        return home_score, away_score
    if row_away == target:
        return away_score, home_score
    if len(row) >= 13:
        flag = _parse_int(row[12])
        if flag == 1:
            return max(home_score, away_score), min(home_score, away_score)
        if flag == 0:
            return home_score, away_score
        if flag == -1:
            return min(home_score, away_score), max(home_score, away_score)
    return None


def _score_agg(
    rows: list | None,
    target_team: str,
    *,
    limit: int = 6,
) -> TitanScoreAgg:
    if not rows:
        return TitanScoreAgg()

    matches_count = goals_for = goals_against = 0
    win_by_1 = win_by_2plus = loss_by_1 = loss_by_2plus = 0
    draw_score_count = one_goal_margin_count = 0
    low_scoring_count = high_scoring_count = 0

    for row in rows[:limit]:
        score = _parse_score_from_row(row, target_team)
        if score is None:
            continue
        gf, ga = score
        margin = gf - ga
        total_goals = gf + ga
        matches_count += 1
        goals_for += gf
        goals_against += ga

        if margin == 0:
            draw_score_count += 1
        elif abs(margin) == 1:
            one_goal_margin_count += 1

        if margin == 1:
            win_by_1 += 1
        elif margin >= 2:
            win_by_2plus += 1
        elif margin == -1:
            loss_by_1 += 1
        elif margin <= -2:
            loss_by_2plus += 1

        if total_goals <= 2:
            low_scoring_count += 1
        if total_goals >= 4:
            high_scoring_count += 1

    return TitanScoreAgg(
        matches_count=matches_count,
        goals_for=goals_for,
        goals_against=goals_against,
        goal_diff=goals_for - goals_against,
        win_by_1=win_by_1,
        win_by_2plus=win_by_2plus,
        loss_by_1=loss_by_1,
        loss_by_2plus=loss_by_2plus,
        draw_score_count=draw_score_count,
        one_goal_margin_count=one_goal_margin_count,
        low_scoring_count=low_scoring_count,
        high_scoring_count=high_scoring_count,
    )


def _extract_array_literal(script: str, start: int) -> str | None:
    depth = 0
    quote: str | None = None
    escaped = False
    for idx in range(start, len(script)):
        ch = script[idx]
        if quote:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == quote:
                quote = None
            continue
        if ch in {"'", '"'}:
            quote = ch
            continue
        if ch == "[":
            depth += 1
        elif ch == "]":
            depth -= 1
            if depth == 0:
                return script[start : idx + 1]
    return None


def _extract_js_array(script: str, var_name: str) -> list | None:
    m = re.search(rf"var\s+{var_name}\s*=\s*", script)
    if m is None:
        return None
    start = script.find("[", m.end())
    if start < 0:
        return None
    raw_literal = _extract_array_literal(script, start)
    if raw_literal is None:
        return None
    raw = _HTML_TAG_RE.sub("", raw_literal)
    try:
        return ast.literal_eval(raw)
    except (ValueError, SyntaxError):
        logger.debug("failed to parse %s", var_name)
        return None


def _wdl(rows: list | None) -> tuple[int, int, int]:
    """Count wins/draws/losses from h_data/a_data style arrays.

    Field [12] is the result flag: 1=win, 0=draw, -1=loss (from the
    perspective of the team in question).
    """
    if not rows:
        return 0, 0, 0
    w = d = lo = 0
    for row in rows:
        if len(row) < 13:
            continue
        try:
            flag = int(row[12])
        except (TypeError, ValueError):
            continue
        if flag == 1:
            w += 1
        elif flag == 0:
            d += 1
        elif flag == -1:
            lo += 1
    return w, d, lo


def _recent_form(rows: list | None, limit: int = 6) -> str | None:
    """Build a WDL string from the most recent ``limit`` matches."""
    if not rows:
        return None
    chars: list[str] = []
    for row in rows[:limit]:
        if len(row) < 13:
            continue
        try:
            flag = int(row[12])
        except (TypeError, ValueError):
            continue
        if flag == 1:
            chars.append("W")
        elif flag == 0:
            chars.append("D")
        else:
            chars.append("L")
    return "".join(chars) if chars else None


def _extract_rank(text: str, team_name: str) -> int | None:
    """Extract the league rank for ``team_name`` from HTML span titles.

    Titan007 embeds ranking like: ``<span title="神户胜利船  排名:日职联1">``
    or ``<span title="神户胜利船  排名:1">``.  We grab the trailing digits.
    """
    pattern = rf'title="{re.escape(team_name)}\s*排名{_COLON_PATTERN}([^"]+)"'
    matches = re.findall(pattern, text)
    if not matches:
        return None
    rank_str = matches[0]
    m = _RANK_RE.search(f"排名:{rank_str}")
    if m:
        return int(m.group(1))
    digits = re.search(r"(\d+)$", rank_str)
    if digits:
        return int(digits.group(1))
    return None


def parse_analysis(html: str, home_team: str, away_team: str) -> TitanTeamStats | None:
    """Parse one analysis page and return aggregated team stats."""
    if not html:
        return None

    scripts = _SCRIPT_RE.findall(html)
    big_script = ""
    for s in scripts:
        if "h_data" in s:
            big_script = s
            break
    if not big_script:
        return None

    h_data = _extract_js_array(big_script, "h_data")
    a_data = _extract_js_array(big_script, "a_data")
    h2_data = _extract_js_array(big_script, "h2_data")
    a2_data = _extract_js_array(big_script, "a2_data")
    v_data = _extract_js_array(big_script, "v_data")

    hw, hd, hl = _wdl(h_data)
    aw, ad, al = _wdl(a_data)
    hhw, hhd, hhl = _wdl(h2_data)
    aaw, aad, aal = _wdl(a2_data)
    home_recent_score = _score_agg(h_data, home_team)
    away_recent_score = _score_agg(a_data, away_team)
    home_home_recent_score = _score_agg(h2_data, home_team)
    away_away_recent_score = _score_agg(a2_data, away_team)
    h2h_score = _score_agg(v_data, home_team)

    vw = vd = vl = 0
    if v_data:
        for row in v_data:
            if len(row) < 13:
                continue
            try:
                flag = int(row[12])
            except (TypeError, ValueError):
                continue
            if flag == 1:
                vw += 1
            elif flag == 0:
                vd += 1
            elif flag == -1:
                vl += 1

    return TitanTeamStats(
        home_rank=_extract_rank(html, home_team),
        home_season_wins=hw,
        home_season_draws=hd,
        home_season_losses=hl,
        home_home_wins=hhw,
        home_home_draws=hhd,
        home_home_losses=hhl,
        home_recent_form=_recent_form(h_data),
        away_rank=_extract_rank(html, away_team),
        away_season_wins=aw,
        away_season_draws=ad,
        away_season_losses=al,
        away_away_wins=aaw,
        away_away_draws=aad,
        away_away_losses=aal,
        away_recent_form=_recent_form(a_data),
        h2h_home_wins=vw if v_data else None,
        h2h_draws=vd if v_data else None,
        h2h_away_wins=vl if v_data else None,
        home_recent_matches_count=home_recent_score.matches_count,
        home_recent_goals_for=home_recent_score.goals_for,
        home_recent_goals_against=home_recent_score.goals_against,
        home_recent_goal_diff=home_recent_score.goal_diff,
        home_recent_win_by_1=home_recent_score.win_by_1,
        home_recent_win_by_2plus=home_recent_score.win_by_2plus,
        home_recent_loss_by_1=home_recent_score.loss_by_1,
        home_recent_loss_by_2plus=home_recent_score.loss_by_2plus,
        home_recent_draw_score_count=home_recent_score.draw_score_count,
        home_recent_low_scoring_count=home_recent_score.low_scoring_count,
        home_recent_high_scoring_count=home_recent_score.high_scoring_count,
        away_recent_matches_count=away_recent_score.matches_count,
        away_recent_goals_for=away_recent_score.goals_for,
        away_recent_goals_against=away_recent_score.goals_against,
        away_recent_goal_diff=away_recent_score.goal_diff,
        away_recent_win_by_1=away_recent_score.win_by_1,
        away_recent_win_by_2plus=away_recent_score.win_by_2plus,
        away_recent_loss_by_1=away_recent_score.loss_by_1,
        away_recent_loss_by_2plus=away_recent_score.loss_by_2plus,
        away_recent_draw_score_count=away_recent_score.draw_score_count,
        away_recent_low_scoring_count=away_recent_score.low_scoring_count,
        away_recent_high_scoring_count=away_recent_score.high_scoring_count,
        home_home_recent_matches_count=home_home_recent_score.matches_count,
        home_home_recent_goals_for=home_home_recent_score.goals_for,
        home_home_recent_goals_against=home_home_recent_score.goals_against,
        home_home_recent_goal_diff=home_home_recent_score.goal_diff,
        home_home_recent_win_by_1=home_home_recent_score.win_by_1,
        home_home_recent_win_by_2plus=home_home_recent_score.win_by_2plus,
        home_home_recent_loss_by_1=home_home_recent_score.loss_by_1,
        home_home_recent_loss_by_2plus=home_home_recent_score.loss_by_2plus,
        away_away_recent_matches_count=away_away_recent_score.matches_count,
        away_away_recent_goals_for=away_away_recent_score.goals_for,
        away_away_recent_goals_against=away_away_recent_score.goals_against,
        away_away_recent_goal_diff=away_away_recent_score.goal_diff,
        away_away_recent_win_by_1=away_away_recent_score.win_by_1,
        away_away_recent_win_by_2plus=away_away_recent_score.win_by_2plus,
        away_away_recent_loss_by_1=away_away_recent_score.loss_by_1,
        away_away_recent_loss_by_2plus=away_away_recent_score.loss_by_2plus,
        h2h_matches_count=h2h_score.matches_count if v_data else None,
        h2h_home_goals_for=h2h_score.goals_for if v_data else None,
        h2h_home_goals_against=h2h_score.goals_against if v_data else None,
        h2h_goal_diff=h2h_score.goal_diff if v_data else None,
        h2h_draw_score_count=h2h_score.draw_score_count if v_data else None,
        h2h_one_goal_margin_count=h2h_score.one_goal_margin_count if v_data else None,
        h2h_low_scoring_count=h2h_score.low_scoring_count if v_data else None,
        h2h_high_scoring_count=h2h_score.high_scoring_count if v_data else None,
    )


def fetch_analysis(
    client: httpx.Client,
    titan_match_id: str,
    *,
    retries: int = 3,
    retry_delay: float = 1.0,
) -> str:
    """Fetch the analysis page HTML for a single titan007 match."""
    last_response: httpx.Response | None = None
    for attempt in range(retries + 1):
        for url_template in ANALYSIS_URLS:
            url = url_template.format(match_id=titan_match_id)
            resp = client.get(url, headers=_HEADERS)
            if resp.status_code == 200 and resp.content:
                return resp.content.decode("utf-8", "replace")
            last_response = resp
        if attempt < retries:
            time.sleep(retry_delay * (2 ** attempt))
    if last_response is None:  # pragma: no cover - defensive
        raise RuntimeError("analysis page request was not attempted")
    raise httpx.HTTPStatusError(
        f"analysis page HTTP {last_response.status_code}",
        request=last_response.request,
        response=last_response,
    )
