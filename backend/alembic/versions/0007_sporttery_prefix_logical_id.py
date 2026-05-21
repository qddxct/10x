"""rename match tables to sporttery_* with BIGINT logical id + comments

Revision ID: 0007
Revises: 0006
Create Date: 2026-04-22 21:30:00.000000

This is a **schema reset** for the match sub-system. Historical data in the
old ``matches`` / ``match_*`` tables is dropped intentionally because:

1. The new logical ``id`` (12-digit ``YYYYMMDDWNNN``) cannot be derived from
   the old auto-increment primary keys without re-scraping anyway.
2. We want to prefix all match-related tables with ``sporttery_`` so that
   future non-竞彩 match data can live in parallel namespaces.

The ``leagues``, ``users``, ``model_configs``, ``scrape_logs`` and
``backtest_sessions`` tables stay intact. ``model_configs`` and ``users`` are
preserved (admin / default config survives the migration).
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0007"
down_revision: str | Sequence[str] | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


OLD_TABLES = (
    "match_team_stats",
    "match_scores",
    "match_results",
    "match_odds",
    "matches",
)


def upgrade() -> None:
    for tbl in OLD_TABLES:
        op.execute(f"DROP TABLE IF EXISTS `{tbl}`")

    op.create_table(
        "sporttery_matches",
        sa.Column(
            "id", sa.BigInteger(), autoincrement=False, nullable=False,
            comment="逻辑ID: YYYYMMDD + 星期(0=周日..6=周六) + 编号3位",
        ),
        sa.Column(
            "sporttery_match_id", sa.String(length=32), nullable=True,
            comment="竞彩官网 webapi.sporttery.cn 内部 matchId; 仅体彩有元数据时有值",
        ),
        sa.Column(
            "match_date", sa.DateTime(), nullable=False,
            comment="开赛时间(北京时间)",
        ),
        sa.Column(
            "league_id", sa.Integer(), nullable=False,
            comment="联赛 FK → leagues.id",
        ),
        sa.Column(
            "home_team", sa.String(length=64), nullable=False,
            comment="主队中文名(简体)",
        ),
        sa.Column(
            "away_team", sa.String(length=64), nullable=False,
            comment="客队中文名(简体)",
        ),
        sa.Column(
            "round", sa.String(length=32), nullable=True,
            comment="竞彩编号(如 周日001)",
        ),
        sa.Column(
            "competition_type",
            sa.Enum(
                "league", "cup", "knockout_first_leg", "knockout_second_leg",
                name="competition_type",
            ),
            nullable=False,
            comment="赛事类型: 联赛/杯赛/淘汰赛首回合/次回合",
        ),
        sa.Column(
            "status",
            sa.Enum("scheduled", "in_progress", "finished", name="match_status"),
            nullable=False,
            comment="比赛状态: 未开赛/进行中/已结束",
        ),
        sa.Column(
            "created_at", sa.DateTime(),
            server_default=sa.text("now()"), nullable=False,
        ),
        sa.Column(
            "updated_at", sa.DateTime(),
            server_default=sa.text("now()"), nullable=False,
        ),
        sa.ForeignKeyConstraint(["league_id"], ["leagues.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        comment="竞彩比赛主表",
    )
    op.create_index(
        "ix_sporttery_matches_date_league",
        "sporttery_matches",
        ["match_date", "league_id"],
    )
    op.create_index(
        op.f("ix_sporttery_matches_league_id"),
        "sporttery_matches", ["league_id"],
    )
    op.create_index(
        op.f("ix_sporttery_matches_match_date"),
        "sporttery_matches", ["match_date"],
    )
    op.create_index(
        op.f("ix_sporttery_matches_sporttery_match_id"),
        "sporttery_matches", ["sporttery_match_id"], unique=True,
    )
    op.create_index(
        op.f("ix_sporttery_matches_status"),
        "sporttery_matches", ["status"],
    )

    op.create_table(
        "sporttery_match_odds",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False, comment="主键"),
        sa.Column(
            "match_id", sa.BigInteger(), nullable=False,
            comment="比赛 FK → sporttery_matches.id (逻辑ID)",
        ),
        sa.Column(
            "source",
            sa.Enum("sporttery", "titan007", "other", name="odds_source"),
            nullable=False,
            comment="赔率来源: sporttery=竞彩官方, titan007=球探网聚合",
        ),
        sa.Column(
            "win_odds", sa.DECIMAL(precision=6, scale=3), nullable=True,
            comment="欧赔主胜(HAD H)",
        ),
        sa.Column(
            "draw_odds", sa.DECIMAL(precision=6, scale=3), nullable=True,
            comment="欧赔平局(HAD D)",
        ),
        sa.Column(
            "lose_odds", sa.DECIMAL(precision=6, scale=3), nullable=True,
            comment="欧赔客胜(HAD A)",
        ),
        sa.Column(
            "handicap_value", sa.DECIMAL(precision=4, scale=2), nullable=True,
            comment="让球值(家球视角,负=让给客队); 如 -1.00, 0.25",
        ),
        sa.Column(
            "win_handicap_odds", sa.DECIMAL(precision=6, scale=3), nullable=True,
            comment="让球主胜(HHAD H)",
        ),
        sa.Column(
            "draw_handicap_odds", sa.DECIMAL(precision=6, scale=3), nullable=True,
            comment="让球平(HHAD D)",
        ),
        sa.Column(
            "lose_handicap_odds", sa.DECIMAL(precision=6, scale=3), nullable=True,
            comment="让球客胜(HHAD A)",
        ),
        sa.Column(
            "asian_handicap", sa.String(length=32), nullable=True,
            comment="亚盘文本描述或让球值字符串(兼容字段)",
        ),
        sa.Column(
            "total_goals", sa.DECIMAL(precision=4, scale=2), nullable=True,
            comment="大小球盘口(若有)",
        ),
        sa.Column(
            "scraped_at", sa.DateTime(), nullable=False, comment="抓取时间(UTC)",
        ),
        sa.Column(
            "created_at", sa.DateTime(),
            server_default=sa.text("now()"), nullable=False,
        ),
        sa.Column(
            "updated_at", sa.DateTime(),
            server_default=sa.text("now()"), nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["match_id"], ["sporttery_matches.id"], ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        comment="竞彩比赛赔率快照: 欧赔+亚盘, 按 source 区分",
    )
    op.create_index(
        op.f("ix_sporttery_match_odds_match_id"),
        "sporttery_match_odds", ["match_id"],
    )
    op.create_index(
        "ix_sporttery_odds_match_source",
        "sporttery_match_odds", ["match_id", "source"],
    )

    op.create_table(
        "sporttery_match_results",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False, comment="主键"),
        sa.Column(
            "match_id", sa.BigInteger(), nullable=False,
            comment="比赛 FK → sporttery_matches.id (逻辑ID)",
        ),
        sa.Column(
            "home_score", sa.SmallInteger(), nullable=False,
            comment="主队全场进球数",
        ),
        sa.Column(
            "away_score", sa.SmallInteger(), nullable=False,
            comment="客队全场进球数",
        ),
        sa.Column(
            "result",
            sa.Enum("home_win", "draw", "away_win", name="match_result_enum"),
            nullable=False,
            comment="胜平负结果(主胜/平/客胜)",
        ),
        sa.Column(
            "handicap_result",
            sa.Enum("home_win", "draw", "away_win", name="handicap_result_enum"),
            nullable=True,
            comment="让球胜平负结果(按 match_odds.handicap_value 计算)",
        ),
        sa.Column(
            "created_at", sa.DateTime(),
            server_default=sa.text("now()"), nullable=False,
        ),
        sa.Column(
            "updated_at", sa.DateTime(),
            server_default=sa.text("now()"), nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["match_id"], ["sporttery_matches.id"], ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("match_id"),
        comment="竞彩比赛结果: 全场比分 + 胜平负 + 让球胜平负",
    )

    op.create_table(
        "sporttery_match_scores",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False, comment="主键"),
        sa.Column(
            "match_id", sa.BigInteger(), nullable=False,
            comment="比赛 FK → sporttery_matches.id (逻辑ID)",
        ),
        sa.Column(
            "model_config_id", sa.Integer(), nullable=False,
            comment="模型配置 FK → model_configs.id",
        ),
        sa.Column(
            "user_id", sa.Integer(), nullable=True,
            comment="操作用户 FK → users.id (系统自动评分时为 NULL)",
        ),
        sa.Column(
            "euro_score", sa.Integer(), nullable=False,
            comment="欧赔维度得分(0-25)",
        ),
        sa.Column(
            "asian_score", sa.Integer(), nullable=False,
            comment="亚盘维度得分(0-20)",
        ),
        sa.Column(
            "goals_score", sa.Integer(), nullable=False,
            comment="进球数维度得分(0-20)",
        ),
        sa.Column(
            "intent_score", sa.Integer(), nullable=False,
            comment="赛事意向维度得分(0-15)",
        ),
        sa.Column(
            "compression_score", sa.Integer(), nullable=False,
            comment="压缩强度维度得分(0-20)",
        ),
        sa.Column(
            "team_stats_score", sa.Integer(), nullable=False,
            comment="球队统计维度得分(0-20)",
        ),
        sa.Column(
            "total_score", sa.Integer(), nullable=False,
            comment="加权后总分",
        ),
        sa.Column(
            "bet_type",
            sa.Enum("draw", "handicap_draw", name="bet_type"),
            nullable=True,
            comment="推荐投注类型: draw=买平, handicap_draw=让球平",
        ),
        sa.Column(
            "kelly_pct", sa.DECIMAL(precision=5, scale=4), nullable=True,
            comment="Kelly 建议投注比例(本金占比)",
        ),
        sa.Column(
            "is_recommended", sa.Boolean(), nullable=False,
            comment="是否达到推荐阈值",
        ),
        sa.Column(
            "actual_hit", sa.Boolean(), nullable=True,
            comment="实际是否命中(结算后回写)",
        ),
        sa.Column(
            "bet_amount", sa.DECIMAL(precision=12, scale=2), nullable=True,
            comment="实际投注金额(CNY)",
        ),
        sa.Column(
            "notes", sa.Text(), nullable=True, comment="操作备注",
        ),
        sa.Column(
            "created_at", sa.DateTime(),
            server_default=sa.text("now()"), nullable=False,
        ),
        sa.Column(
            "updated_at", sa.DateTime(),
            server_default=sa.text("now()"), nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["match_id"], ["sporttery_matches.id"], ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["model_config_id"], ["model_configs.id"], ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "match_id", "model_config_id", name="uq_sporttery_scores_match_config",
        ),
        comment="竞彩比赛 6 维评分: 欧赔/亚盘/进球数/意向/压缩/球队统计",
    )
    op.create_index(
        op.f("ix_sporttery_match_scores_match_id"),
        "sporttery_match_scores", ["match_id"],
    )
    op.create_index(
        op.f("ix_sporttery_match_scores_model_config_id"),
        "sporttery_match_scores", ["model_config_id"],
    )
    op.create_index(
        op.f("ix_sporttery_match_scores_user_id"),
        "sporttery_match_scores", ["user_id"],
    )
    op.create_index(
        op.f("ix_sporttery_match_scores_total_score"),
        "sporttery_match_scores", ["total_score"],
    )
    op.create_index(
        op.f("ix_sporttery_match_scores_is_recommended"),
        "sporttery_match_scores", ["is_recommended"],
    )

    op.create_table(
        "sporttery_match_team_stats",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False, comment="主键"),
        sa.Column(
            "match_id", sa.BigInteger(), nullable=False,
            comment="比赛 FK → sporttery_matches.id (逻辑ID)",
        ),
        sa.Column("home_rank", sa.SmallInteger(), nullable=True, comment="主队联赛排名"),
        sa.Column("home_season_wins", sa.SmallInteger(), nullable=True, comment="主队赛季胜场"),
        sa.Column("home_season_draws", sa.SmallInteger(), nullable=True, comment="主队赛季平场"),
        sa.Column("home_season_losses", sa.SmallInteger(), nullable=True, comment="主队赛季负场"),
        sa.Column("home_home_wins", sa.SmallInteger(), nullable=True, comment="主队主场胜"),
        sa.Column("home_home_draws", sa.SmallInteger(), nullable=True, comment="主队主场平"),
        sa.Column("home_home_losses", sa.SmallInteger(), nullable=True, comment="主队主场负"),
        sa.Column(
            "home_recent_form", sa.String(length=16), nullable=True,
            comment="主队近 5-10 场战绩串(W/D/L)",
        ),
        sa.Column("away_rank", sa.SmallInteger(), nullable=True, comment="客队联赛排名"),
        sa.Column("away_season_wins", sa.SmallInteger(), nullable=True, comment="客队赛季胜场"),
        sa.Column("away_season_draws", sa.SmallInteger(), nullable=True, comment="客队赛季平场"),
        sa.Column("away_season_losses", sa.SmallInteger(), nullable=True, comment="客队赛季负场"),
        sa.Column("away_away_wins", sa.SmallInteger(), nullable=True, comment="客队客场胜"),
        sa.Column("away_away_draws", sa.SmallInteger(), nullable=True, comment="客队客场平"),
        sa.Column("away_away_losses", sa.SmallInteger(), nullable=True, comment="客队客场负"),
        sa.Column(
            "away_recent_form", sa.String(length=16), nullable=True,
            comment="客队近 5-10 场战绩串(W/D/L)",
        ),
        sa.Column("h2h_home_wins", sa.SmallInteger(), nullable=True, comment="交锋:主队胜场"),
        sa.Column("h2h_draws", sa.SmallInteger(), nullable=True, comment="交锋:平场"),
        sa.Column("h2h_away_wins", sa.SmallInteger(), nullable=True, comment="交锋:客队胜场"),
        sa.Column("scraped_at", sa.DateTime(), nullable=False, comment="抓取时间(UTC)"),
        sa.Column(
            "created_at", sa.DateTime(),
            server_default=sa.text("now()"), nullable=False,
        ),
        sa.Column(
            "updated_at", sa.DateTime(),
            server_default=sa.text("now()"), nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["match_id"], ["sporttery_matches.id"], ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("match_id"),
        comment="球队战绩快照: 排名/赛季战绩/主客场/近况/交锋",
    )


def downgrade() -> None:
    op.drop_table("sporttery_match_team_stats")
    op.drop_table("sporttery_match_scores")
    op.drop_table("sporttery_match_results")
    op.drop_table("sporttery_match_odds")
    op.drop_table("sporttery_matches")
