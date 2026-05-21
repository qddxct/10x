from __future__ import annotations

import httpx
from app.scrapers.titan007.analysis import fetch_analysis, parse_analysis


def _row(flag: int | str) -> list:
    row = [0] * 13
    row[12] = flag
    return row


def _score_row(
    target_team: str,
    opponent_team: str,
    *,
    target_is_home: bool,
    home_score: int | str,
    away_score: int | str,
    flag: int | str,
) -> list:
    row = [0] * 22
    row[5] = target_team if target_is_home else opponent_team
    row[7] = opponent_team if target_is_home else target_team
    row[8] = home_score
    row[9] = away_score
    row[12] = flag
    return row


def test_parse_analysis_extracts_historical_team_stats():
    html = f"""
    <html>
      <span title="浦和红钻排名:日职联3"></span>
      <span title="鹿岛鹿角  排名:日职联5"></span>
      <script>
        var h_data = {[_row(1), _row(0), _row(-1), _row("1"), _row("0"), _row("-1")]};
        var a_data = {[_row(-1), _row(0), _row(0), _row(1)]};
        var h2_data = {[_row(1), _row(1), _row(0)]};
        var a2_data = {[_row(-1), _row(0), _row(-1)]};
        var v_data = {[_row(1), _row(0), _row(-1), _row(0)]};
      </script>
    </html>
    """

    stats = parse_analysis(html, "浦和红钻", "鹿岛鹿角")

    assert stats is not None
    assert stats.home_rank == 3
    assert stats.away_rank == 5
    assert stats.home_season_wins == 2
    assert stats.home_season_draws == 2
    assert stats.home_season_losses == 2
    assert stats.home_home_wins == 2
    assert stats.home_home_draws == 1
    assert stats.away_season_wins == 1
    assert stats.away_season_draws == 2
    assert stats.away_season_losses == 1
    assert stats.away_away_draws == 1
    assert stats.home_recent_form == "WDLWDL"
    assert stats.away_recent_form == "LDDW"
    assert stats.h2h_home_wins == 1
    assert stats.h2h_draws == 2
    assert stats.h2h_away_wins == 1


def test_parse_analysis_extracts_recent_score_shape():
    h_data = [
        _score_row("浦和红钻", "横滨水手", target_is_home=False, home_score=0, away_score=2, flag=1),
        _score_row("浦和红钻", "FC东京", target_is_home=False, home_score=1, away_score=1, flag=0),
        _score_row("浦和红钻", "千叶市原", target_is_home=True, home_score=0, away_score=1, flag=-1),
        _score_row("浦和红钻", "大阪钢巴", target_is_home=True, home_score=2, away_score=0, flag=1),
        _score_row("浦和红钻", "广岛三箭", target_is_home=False, home_score=2, away_score=0, flag=-1),
        _score_row("浦和红钻", "札幌冈萨多", target_is_home=True, home_score=2, away_score=2, flag=0),
        _score_row("浦和红钻", "无效比分", target_is_home=True, home_score="", away_score="", flag=0),
    ]
    a_data = [
        _score_row("鹿岛鹿角1", "柏太阳神", target_is_home=True, home_score=2, away_score=0, flag=1),
        _score_row("鹿岛鹿角", "横滨水手", target_is_home=True, home_score=1, away_score=0, flag=1),
        _score_row("鹿岛鹿角", "FC东京", target_is_home=False, home_score=1, away_score=1, flag=0),
        _score_row("鹿岛鹿角", "大阪樱花", target_is_home=False, home_score=3, away_score=1, flag=-1),
    ]
    h2_data = [
        _score_row("浦和红钻", "川崎前锋", target_is_home=True, home_score=4, away_score=0, flag=1),
        _score_row("浦和红钻", "町田泽维亚", target_is_home=True, home_score=0, away_score=0, flag=0),
        _score_row("浦和红钻", "神户胜利船", target_is_home=True, home_score=1, away_score=0, flag=1),
    ]
    a2_data = [
        _score_row("鹿岛鹿角1", "FC东京", target_is_home=False, home_score=1, away_score=1, flag=0),
        _score_row("鹿岛鹿角", "东京绿茵", target_is_home=False, home_score=0, away_score=1, flag=1),
        _score_row("鹿岛鹿角", "京都不死鸟", target_is_home=False, home_score=3, away_score=1, flag=-1),
    ]
    v_data = [
        _score_row("浦和红钻", "鹿岛鹿角", target_is_home=True, home_score=0, away_score=1, flag=-1),
        _score_row("浦和红钻", "鹿岛鹿角", target_is_home=False, home_score=1, away_score=1, flag=0),
        _score_row("浦和红钻", "鹿岛鹿角", target_is_home=False, home_score=0, away_score=2, flag=1),
    ]
    html = f"""
    <html>
      <span title="浦和红钻排名:日职联3"></span>
      <span title="鹿岛鹿角  排名:日职联5"></span>
      <script>
        var h_data = {h_data};
        var a_data = {a_data};
        var h2_data = {h2_data};
        var a2_data = {a2_data};
        var v_data = {v_data};
      </script>
    </html>
    """

    stats = parse_analysis(html, "浦和红钻", "鹿岛鹿角")

    assert stats is not None
    assert stats.home_recent_matches_count == 6
    assert stats.home_recent_goals_for == 7
    assert stats.home_recent_goals_against == 6
    assert stats.home_recent_goal_diff == 1
    assert stats.home_recent_win_by_1 == 0
    assert stats.home_recent_win_by_2plus == 2
    assert stats.home_recent_loss_by_1 == 1
    assert stats.home_recent_loss_by_2plus == 1
    assert stats.home_recent_draw_score_count == 2
    assert stats.home_recent_low_scoring_count == 5
    assert stats.home_recent_high_scoring_count == 1

    assert stats.away_recent_matches_count == 4
    assert stats.away_recent_goals_for == 5
    assert stats.away_recent_goals_against == 4
    assert stats.away_recent_goal_diff == 1
    assert stats.away_recent_win_by_1 == 1
    assert stats.away_recent_loss_by_2plus == 1
    assert stats.away_recent_draw_score_count == 1

    assert stats.home_home_recent_matches_count == 3
    assert stats.home_home_recent_goals_for == 5
    assert stats.home_home_recent_goals_against == 0
    assert stats.home_home_recent_win_by_1 == 1
    assert stats.home_home_recent_win_by_2plus == 1

    assert stats.away_away_recent_matches_count == 3
    assert stats.away_away_recent_goals_for == 3
    assert stats.away_away_recent_goals_against == 4
    assert stats.away_away_recent_loss_by_2plus == 1

    assert stats.h2h_matches_count == 3
    assert stats.h2h_home_goals_for == 3
    assert stats.h2h_home_goals_against == 2
    assert stats.h2h_goal_diff == 1
    assert stats.h2h_draw_score_count == 1
    assert stats.h2h_one_goal_margin_count == 1
    assert stats.h2h_low_scoring_count == 3
    assert stats.h2h_high_scoring_count == 0


def test_parse_analysis_infers_score_direction_when_team_name_is_abbreviated():
    h_data = [
        _score_row("神户胜利船", "浦和红钻", target_is_home=True, home_score=1, away_score=0, flag=1),
        _score_row("神户胜利船", "大阪钢巴", target_is_home=False, home_score=2, away_score=0, flag=-1),
        _score_row("神户胜利船", "鹿岛鹿角", target_is_home=True, home_score=1, away_score=1, flag=0),
    ]
    html = f"""
    <html>
      <script>
        var h_data = {h_data};
        var a_data = [];
        var h2_data = [];
        var a2_data = [];
        var v_data = [];
      </script>
    </html>
    """

    stats = parse_analysis(html, "神户胜利", "浦和红钻")

    assert stats is not None
    assert stats.home_recent_matches_count == 3
    assert stats.home_recent_goals_for == 2
    assert stats.home_recent_goals_against == 3
    assert stats.home_recent_win_by_1 == 1
    assert stats.home_recent_loss_by_2plus == 1
    assert stats.home_recent_draw_score_count == 1


def test_fetch_analysis_uses_cn_analysis_url():
    seen_urls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen_urls.append(str(request.url))
        return httpx.Response(200, text="<html>ok</html>", request=request)

    client = httpx.Client(transport=httpx.MockTransport(handler))

    assert fetch_analysis(client, "2915933") == "<html>ok</html>"
    assert seen_urls == ["https://zq.titan007.com/analysis/2915933cn.htm"]


def test_fetch_analysis_retries_transient_empty_response():
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls == 1:
            return httpx.Response(443, text="", request=request)
        return httpx.Response(200, text="<html>ok</html>", request=request)

    client = httpx.Client(transport=httpx.MockTransport(handler))

    assert fetch_analysis(client, "2915933", retry_delay=0) == "<html>ok</html>"
    assert calls == 2
